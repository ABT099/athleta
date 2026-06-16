<?php
/**
 * Kafka worker for the muscle-image service.
 *
 * Consumes `athleta.workout-day.created` events from the api, renders the
 * corresponding muscle image (deduping identical renders via a content-
 * addressed R2 key), and publishes `athleta.muscle-image.generated` with the
 * resulting URL so the api can persist it on the workout day.
 *
 * Run as a long-lived process: `php consumer.php`.
 */

require_once __DIR__ . '/vendor/autoload.php';
require_once __DIR__ . '/controllers/MuscleImageController.php';
require_once __DIR__ . '/util/R2Uploader.php';

// The controller resolves overlay images via relative paths (./resources/...),
// so anchor the working directory to the app root regardless of launch dir.
chdir(__DIR__);

const WORKOUT_DAY_CREATED_TOPIC = 'athleta.workout-day.created';
const MUSCLE_IMAGE_GENERATED_TOPIC = 'athleta.muscle-image.generated';
const CONSUMER_GROUP = 'muscle-image-workers';

function logLine(string $level, string $msg): void {
    fwrite(STDOUT, sprintf("[%s] %s %s\n", date('c'), $level, $msg));
}

$brokers = getenv('KAFKA_BROKERS') ?: 'localhost:9092';

// --- Producer (result events) -------------------------------------------------
$producerConf = new RdKafka\Conf();
$producerConf->set('metadata.broker.list', $brokers);
$producer = new RdKafka\Producer($producerConf);
$resultTopic = $producer->newTopic(MUSCLE_IMAGE_GENERATED_TOPIC);

// --- Consumer -----------------------------------------------------------------
$conf = new RdKafka\Conf();
$conf->set('metadata.broker.list', $brokers);
$conf->set('group.id', CONSUMER_GROUP);
$conf->set('auto.offset.reset', 'earliest');
$conf->set('enable.auto.commit', 'true');
$conf->set('auto.commit.interval.ms', '1000');

$consumer = new RdKafka\KafkaConsumer($conf);
$consumer->subscribe([WORKOUT_DAY_CREATED_TOPIC]);

$r2 = new R2Uploader();

logLine('INFO', "muscle-image worker started; brokers={$brokers}, group=" . CONSUMER_GROUP);

while (true) {
    $message = $consumer->consume(10000); // 10s poll timeout
    switch ($message->err) {
        case RD_KAFKA_RESP_ERR_NO_ERROR:
            handleMessage($message, $r2, $producer, $resultTopic);
            break;
        case RD_KAFKA_RESP_ERR__PARTITION_EOF:
        case RD_KAFKA_RESP_ERR__TIMED_OUT:
            // Nothing waiting; keep polling.
            break;
        default:
            logLine('ERROR', 'Kafka consume error: ' . $message->errstr());
            break;
    }
}

/**
 * Render (or reuse) the image for one workout-day-created event and publish the
 * result. Failures are logged and swallowed so one bad message can't stall the
 * worker; the content-addressed key makes reprocessing idempotent.
 */
function handleMessage($message, R2Uploader $r2, RdKafka\Producer $producer, RdKafka\ProducerTopic $resultTopic): void {
    $payload = json_decode($message->payload, true);
    if (!is_array($payload) || !isset($payload['workoutDayId'])) {
        logLine('WARN', 'Skipping malformed message: ' . $message->payload);
        return;
    }

    $workoutDayId = $payload['workoutDayId'];
    $muscles = $payload['muscles'] ?? [];

    try {
        $split = MuscleImageController::splitMuscles($muscles);
        $primaryCsv = implode(',', $split['primary']);
        $secondaryCsv = implode(',', $split['secondary']);

        if ($primaryCsv === '' && $secondaryCsv === '') {
            logLine('WARN', "No renderable muscles for workout day {$workoutDayId}; skipping");
            return;
        }

        $primaryColor = MuscleImageController::DEFAULT_PRIMARY_COLOR;
        $secondaryColor = MuscleImageController::DEFAULT_SECONDARY_COLOR;
        $key = MuscleImageController::imageKey($primaryCsv, $secondaryCsv, $primaryColor, $secondaryColor);

        if ($r2->objectExists($key)) {
            $url = $r2->urlFor($key);
            logLine('INFO', "Image already exists for workout day {$workoutDayId}, reusing {$key}");
        } else {
            $url = MuscleImageController::renderAndUpload(
                $primaryCsv,
                $secondaryCsv,
                $primaryColor,
                $secondaryColor,
                $key
            );
            logLine('INFO', "Generated image for workout day {$workoutDayId} -> {$key}");
        }

        publishResult($producer, $resultTopic, $workoutDayId, $url);
    } catch (Throwable $e) {
        logLine('ERROR', "Failed to process workout day {$workoutDayId}: " . $e->getMessage());
    }
}

function publishResult(RdKafka\Producer $producer, RdKafka\ProducerTopic $topic, $workoutDayId, string $url): void {
    $value = json_encode(['workoutDayId' => $workoutDayId, 'url' => $url]);
    $topic->produce(RD_KAFKA_PARTITION_UA, 0, $value, (string) $workoutDayId);
    $producer->poll(0);

    // Block briefly to ensure delivery before moving on.
    for ($i = 0; $i < 10 && $producer->getOutQLen() > 0; $i++) {
        $producer->flush(1000);
    }

    logLine('INFO', 'Published ' . MUSCLE_IMAGE_GENERATED_TOPIC . " for workout day {$workoutDayId}");
}
