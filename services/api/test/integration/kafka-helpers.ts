import { Kafka, logLevel } from 'kafkajs';

function brokerList(): string[] {
  return (process.env.KAFKA_BROKERS || 'localhost:9092').split(',');
}

function makeKafka(clientId: string): Kafka {
  return new Kafka({
    clientId,
    brokers: brokerList(),
    logLevel: logLevel.NOTHING,
  });
}

/** Produce a raw JSON event (matching how Nest serializes emitted values). */
export async function produceEvent(
  topic: string,
  value: unknown,
  key?: string,
): Promise<void> {
  const producer = makeKafka('it-producer').producer();
  await producer.connect();
  await producer.send({
    topic,
    messages: [{ key, value: JSON.stringify(value) }],
  });
  await producer.disconnect();
}

export interface MessageCollector {
  messages: Array<Record<string, unknown>>;
  stop: () => Promise<void>;
}

/**
 * Start collecting messages on a topic under a throwaway group. Defaults to only
 * new messages (`fromBeginning: false`) so assertions aren't confused by events
 * left on the topic by earlier tests (Kafka isn't reset between tests, but
 * Postgres identities are). Allow the returned collector a moment to finish
 * joining the group before publishing the message under test.
 */
export async function collectMessages(
  topic: string,
  { fromBeginning = false } = {},
): Promise<MessageCollector> {
  const consumer = makeKafka('it-collector').consumer({
    groupId: `it-collector-${Date.now()}-${Math.floor(Math.random() * 1e6)}`,
  });
  await consumer.connect();
  await consumer.subscribe({ topic, fromBeginning });

  const messages: Array<Record<string, unknown>> = [];
  await consumer.run({
    eachMessage: async ({ message }) => {
      try {
        messages.push(JSON.parse(message.value!.toString()));
      } catch {
        /* ignore non-JSON */
      }
    },
  });
  // Give the group a moment to settle so post-subscribe publishes are captured.
  await new Promise((r) => setTimeout(r, 1500));

  return { messages, stop: () => consumer.disconnect() };
}

/** Poll until `predicate` holds over the produced value, or time out. */
export async function waitFor<T>(
  produce: () => T | Promise<T>,
  predicate: (value: T) => boolean,
  { timeoutMs = 25000, intervalMs = 500 } = {},
): Promise<T> {
  const start = Date.now();
  let last: T = await produce();
  while (Date.now() - start < timeoutMs) {
    if (predicate(last)) return last;
    await new Promise((r) => setTimeout(r, intervalMs));
    last = await produce();
  }
  throw new Error('waitFor timed out');
}
