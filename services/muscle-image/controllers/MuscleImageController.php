<?php

require_once __DIR__ . '/../util/R2Uploader.php';

class MuscleImageController {

    static array $availableMuscleGroups = array(
        "all",
        "all_lower",
        "all_upper",
        "abductors",
        "abs",
        "adductors",
        "back",
        "back_lower",
        "back_upper",
        "biceps",
        "calfs",
        "chest",
        "core",
        "core_lower",
        "core_upper",
        "forearms",
        "gluteus",
        "hamstring",
        "hands",
        "latissimus",
        "legs",
        "neck",
        "quadriceps",
        "shoulders",
        "shoulders_back",
        "shoulders_front",
        "triceps"
    );

    public static function getMuscleGroups() {

        header('Content-Type: application/json');
        header("Access-Control-Allow-Origin: *");

        echo json_encode(MuscleImageController::$availableMuscleGroups, JSON_PRETTY_PRINT);
    }

    public static function testCreateImage() {

        header('Content-Type: plain/text');
        header("Access-Control-Allow-Origin: *");

        $im = imagecreatetruecolor(120, 20);
        $text_color = imagecolorallocate($im, 233, 14, 91);
        imagestring($im, 1, 5, 5,  'A Simple Text String', $text_color);
        var_dump($im);
        imagepng($im);
        imagedestroy($im);
    }

    public static function getBaseImage($transparentBackground) {
        header('Content-Type: image/png');
        header("Access-Control-Allow-Origin: *");

        if ($transparentBackground == null || $transparentBackground == 0) {
            $baseImage = imagecreatefrompng('./resources/images/baseImage.png');
        } else {
            $baseImage = imagecreatefrompng('./resources/images/baseImage_transparent.png');
        }

        imagepng($baseImage);
        imagedestroy($baseImage);
    }

    public static function getMuscleImage($muscleGroupsQuery, $transparentBackground) {

        header('Content-Type: image/png');
        header("Access-Control-Allow-Origin: *");

        if ($transparentBackground == null || $transparentBackground == 0) {
            $baseImage = imagecreatefrompng('./resources/images/baseImage.png');
        } else {
            $baseImage = imagecreatefrompng('./resources/images/baseImage_transparent.png');
        }

        $muscleGroups = explode(",", $muscleGroupsQuery);
        foreach ($muscleGroups as $muscleGroup) {

            if (!in_array($muscleGroup, MuscleImageController::$availableMuscleGroups)) {
                http_response_code(400);
                exit;
            }

            $muscleGroupImage = imagecreatefrompng('./resources/images/' . $muscleGroup . '.png');

            imagealphablending($baseImage, false);
            imagesavealpha($baseImage, true);

            imagecopymerge($baseImage, $muscleGroupImage, 0, 0, 0, 0, 1920, 1920, 100);
            imagedestroy($muscleGroupImage);
        }

        imagepng($baseImage);
        imagedestroy($baseImage);
    }

    public static function getMuscleImageWithCustomColor($muscleGroupsQuery, $colorQuery, $transparentBackground) {

        header('Content-Type: image/png');
        header("Access-Control-Allow-Origin: *");

        if ($transparentBackground == null || $transparentBackground == 0) {
            $baseImage = imagecreatefrompng('./resources/images/baseImage.png');
        } else {
            $baseImage = imagecreatefrompng('./resources/images/baseImage_transparent.png');
        }
        $colorRgb = explode(",", $colorQuery);

        $muscleGroups = explode(",", $muscleGroupsQuery);
        foreach ($muscleGroups as $muscleGroup) {

            if (!in_array($muscleGroup, MuscleImageController::$availableMuscleGroups)) {
                http_response_code(400);
                exit;
            }

            $muscleGroupImage = imagecreatefrompng('./resources/images/' . $muscleGroup . '.png');

            $index = imagecolorexact($muscleGroupImage,89,136,255);
            imagecolorset($muscleGroupImage, $index, $colorRgb[0], $colorRgb[1], $colorRgb[2]);

            imagealphablending($baseImage, false);
            imagesavealpha($baseImage, true);

            imagecopymerge($baseImage, $muscleGroupImage, 0, 0, 0, 0, 1920, 1920, 100);
            imagedestroy($muscleGroupImage);
        }

        imagepng($baseImage);
        imagedestroy($baseImage);
    }

    public static function getMuscleImageWithMultiColor($primaryMuscleGroupsQuery, $secondaryMuscleGroupsQuery, $primaryColorQuery, $secondaryColorQuery, $transparentBackground) {

        header('Content-Type: image/png');
        header("Access-Control-Allow-Origin: *");

        if ($transparentBackground == null || $transparentBackground == 0) {
            $baseImage = imagecreatefrompng('./resources/images/baseImage.png');
        } else {
            $baseImage = imagecreatefrompng('./resources/images/baseImage_transparent.png');
        }
        $primaryColorRgb = explode(",", $primaryColorQuery);
        $secondaryColorRgb = explode(",", $secondaryColorQuery);


        $primaryMuscleGroups = explode(",", $primaryMuscleGroupsQuery);
        foreach ($primaryMuscleGroups as $muscleGroup) {

            if (!in_array($muscleGroup, MuscleImageController::$availableMuscleGroups)) {
                http_response_code(400);
                exit;
            }

            $muscleGroupImage = imagecreatefrompng('./resources/images/' . $muscleGroup . '.png');

            $index = imagecolorexact($muscleGroupImage,89,136,255);
            imagecolorset($muscleGroupImage, $index, $primaryColorRgb[0], $primaryColorRgb[1], $primaryColorRgb[2]);

            imagealphablending($baseImage, false);
            imagesavealpha($baseImage, true);

            imagecopymerge($baseImage, $muscleGroupImage, 0, 0, 0, 0, 1920, 1920, 100);
            imagedestroy($muscleGroupImage);
        }

        $secondaryMuscleGroups = explode(",", $secondaryMuscleGroupsQuery);
        foreach ($secondaryMuscleGroups as $muscleGroup) {

            if (!in_array($muscleGroup, MuscleImageController::$availableMuscleGroups)) {
                http_response_code(400);
                exit;
            }

            $muscleGroupImage = imagecreatefrompng('./resources/images/' . $muscleGroup . '.png');

            $index = imagecolorexact($muscleGroupImage,89,136,255);
            imagecolorset($muscleGroupImage, $index, $secondaryColorRgb[0], $secondaryColorRgb[1], $secondaryColorRgb[2]);

            imagealphablending($baseImage, false);
            imagesavealpha($baseImage, true);

            imagecopymerge($baseImage, $muscleGroupImage, 0, 0, 0, 0, 1920, 1920, 100);
            imagedestroy($muscleGroupImage);
        }

        imagepng($baseImage);
        imagedestroy($baseImage);
    }

    public static function getIndividualColorImage($muscleGroups, $colors, $transparentBackground) {

        header('Content-Type: image/png');
        header("Access-Control-Allow-Origin: *");

        if ($transparentBackground == null || $transparentBackground == 0) {
            $baseImage = imagecreatefrompng('./resources/images/baseImage.png');
        } else {
            $baseImage = imagecreatefrompng('./resources/images/baseImage_transparent.png');
        }

        $colorsArray = explode(",", $colors);
        $muscleGroupsArray = explode(",", $muscleGroups);

        $counter = 0;
        foreach ($muscleGroupsArray as $muscleGroup) {

            if ($muscleGroup != "") {
                if (!in_array($muscleGroup, MuscleImageController::$availableMuscleGroups)) {
                    http_response_code(400);
                    exit;
                }

                $muscleGroupImage = imagecreatefrompng('./resources/images/' . $muscleGroup . '.png');

                $index = imagecolorexact($muscleGroupImage, 89, 136, 255);
                $rgbColor = self::hex2RGB($colorsArray[$counter]);
                if ($counter < sizeof($colorsArray) - 1) {
                    $counter++;
                }
                imagecolorset($muscleGroupImage, $index, $rgbColor["red"], $rgbColor["green"], $rgbColor["blue"]);

                imagealphablending($baseImage, false);
                imagesavealpha($baseImage, true);

                imagecopymerge($baseImage, $muscleGroupImage, 0, 0, 0, 0, 1920, 1920, 100);
                imagedestroy($muscleGroupImage);
            }
        }

        imagepng($baseImage);
        imagedestroy($baseImage);
    }

    /**
     * Convert a hexa decimal color code to its RGB equivalent
     *
     * @param string $hexStr (hexadecimal color value)
     * @param boolean $returnAsString (if set true, returns the value separated by the separator character. Otherwise returns associative array)
     * @param string $seperator (to separate RGB values. Applicable only if second parameter is true.)
     * @return array or string (depending on second parameter. Returns False if invalid hex color value)
     */
    public static function hex2RGB(string $hexStr, bool $returnAsString = false, string $separator = ',') {
        $hexStr = preg_replace("/[^\dA-Fa-f]/", '', $hexStr); // Gets a proper hex string
        $rgbArray = array();
        if (strlen($hexStr) == 6) { //If a proper hex code, convert using bitwise operation. No overhead... faster
            $colorVal = hexdec($hexStr);
            $rgbArray['red'] = 0xFF & ($colorVal >> 0x10);
            $rgbArray['green'] = 0xFF & ($colorVal >> 0x8);
            $rgbArray['blue'] = 0xFF & $colorVal;
        } elseif (strlen($hexStr) == 3) { //if shorthand notation, need some string manipulations
            $rgbArray['red'] = hexdec(str_repeat(substr($hexStr, 0, 1), 2));
            $rgbArray['green'] = hexdec(str_repeat(substr($hexStr, 1, 1), 2));
            $rgbArray['blue'] = hexdec(str_repeat(substr($hexStr, 2, 1), 2));
        } else {
            http_response_code(400);
            exit; //Invalid hex color code
        }
        return $returnAsString ? implode($separator, $rgbArray) : $rgbArray; // returns the rgb string or the associative array
    }

    const DEFAULT_PRIMARY_COLOR = '255,89,94';
    const DEFAULT_SECONDARY_COLOR = '138,201,38';

    /**
     * Map an api-domain muscle name to this service's image-group vocabulary.
     * Ported from the api so muscle-image owns its own rendering names.
     * Returns null for muscles with no image (caller skips them).
     */
    public static function mapMuscleNameToImageService(string $dbMuscleName): ?string {
        static $mapping = [
            // Chest
            'upper_chest' => 'chest',
            'mid_chest' => 'chest',
            'lower_chest' => 'chest',
            // Back
            'lats' => 'latissimus',
            'upper_traps' => 'back_upper',
            'mid_back' => 'back',
            'lower_traps' => 'back_lower',
            // Shoulders
            'anterior_delt' => 'shoulders_front',
            'lateral_delt' => 'shoulders',
            'posterior_delt' => 'shoulders_back',
            // Arms
            'biceps' => 'biceps',
            'triceps' => 'triceps',
            'forearms' => 'forearms',
            // Legs
            'quadriceps' => 'quadriceps',
            'hamstrings' => 'hamstring',
            'glutes' => 'gluteus',
            'hip_flexors' => 'core_lower',
            'calves' => 'calfs',
            // Core
            'abs' => 'abs',
            'erector_spinae' => 'back_lower',
        ];

        return $mapping[$dbMuscleName] ?? null;
    }

    /**
     * Split raw {name, role} muscle targets into deduped primary/secondary
     * image groups. prime_mover -> primary; synergist/stabilizer -> secondary.
     *
     * @param array $muscles list of ['name' => string, 'role' => string]
     * @return array{primary: string[], secondary: string[]}
     */
    public static function splitMuscles(array $muscles): array {
        $primary = [];
        $secondary = [];

        foreach ($muscles as $muscle) {
            $mapped = self::mapMuscleNameToImageService($muscle['name'] ?? '');
            if ($mapped === null) {
                continue;
            }
            $role = $muscle['role'] ?? '';
            if ($role === 'prime_mover') {
                $primary[$mapped] = true;
            } elseif ($role === 'synergist' || $role === 'stabilizer') {
                $secondary[$mapped] = true;
            }
        }

        return [
            'primary' => array_keys($primary),
            'secondary' => array_keys($secondary),
        ];
    }

    /**
     * Deterministic, content-addressed R2 object key for a muscle image. Two
     * workout days with the same groups + colours resolve to the same key,
     * which lets the worker skip regeneration (dedupe).
     */
    public static function imageKey(string $primaryCsv, string $secondaryCsv, string $primaryColor, string $secondaryColor): string {
        $hash = sha1("{$primaryCsv}|{$secondaryCsv}|{$primaryColor}|{$secondaryColor}");
        return "muscle-images/{$hash}.png";
    }

    /**
     * HTTP entrypoint: generate a muscle image and upload to R2 (keyed by
     * workout day for backwards compatibility), returning JSON with the URL.
     */
    public static function generateAndStoreImage($workoutDayId, $primaryMuscleGroupsQuery, $secondaryMuscleGroupsQuery, $primaryColorQuery, $secondaryColorQuery) {
        header('Content-Type: application/json');
        header("Access-Control-Allow-Origin: *");

        try {
            $imageUrl = self::renderAndUpload(
                $primaryMuscleGroupsQuery,
                $secondaryMuscleGroupsQuery,
                $primaryColorQuery,
                $secondaryColorQuery,
                "muscle-images/{$workoutDayId}.png"
            );
            echo json_encode(['url' => $imageUrl]);
        } catch (InvalidArgumentException $e) {
            http_response_code(400);
            echo json_encode(['error' => $e->getMessage()]);
        } catch (Exception $e) {
            http_response_code(500);
            echo json_encode(['error' => 'Failed to generate and upload image: ' . $e->getMessage()]);
        }
    }

    /**
     * Render a muscle image at 800x800 from comma-separated primary/secondary
     * groups, then upload it to R2 under $key. Returns the public R2 URL.
     *
     * @throws InvalidArgumentException on an unknown muscle group
     * @throws RuntimeException on a rendering/upload failure
     */
    public static function renderAndUpload(string $primaryMuscleGroupsQuery, string $secondaryMuscleGroupsQuery, string $primaryColorQuery, string $secondaryColorQuery, string $key): string {
        // Try to load 800x800 base image, fallback to 1920x1920 and resize
        $baseImagePath800 = './resources/images/baseImage_800.png';
        $baseImagePath = './resources/images/baseImage.png';

        if (file_exists($baseImagePath800)) {
            $baseImage = imagecreatefrompng($baseImagePath800);
        } else {
            // Load 1920x1920 and resize to 800x800
            $sourceImage = imagecreatefrompng($baseImagePath);
            $baseImage = imagecreatetruecolor(800, 800);
            imagealphablending($baseImage, false);
            imagesavealpha($baseImage, true);
            imagecopyresampled($baseImage, $sourceImage, 0, 0, 0, 0, 800, 800, 1920, 1920);
            imagedestroy($sourceImage);
        }

        if (!$baseImage) {
            throw new RuntimeException('Failed to create base image');
        }

        try {
            self::overlayMuscles($baseImage, $primaryMuscleGroupsQuery, $primaryColorQuery);
            self::overlayMuscles($baseImage, $secondaryMuscleGroupsQuery, $secondaryColorQuery);

            $r2Uploader = new R2Uploader();
            return $r2Uploader->uploadImage($baseImage, $key);
        } finally {
            imagedestroy($baseImage);
        }
    }

    /**
     * Overlay each comma-separated muscle group onto $baseImage, recoloured to
     * $colorQuery (RGB "r,g,b"). Scales the 1920x1920 overlays down to 800x800.
     *
     * @throws InvalidArgumentException on an unknown muscle group
     */
    private static function overlayMuscles($baseImage, string $muscleGroupsQuery, string $colorQuery): void {
        if (empty($muscleGroupsQuery)) {
            return;
        }

        $colorRgb = explode(",", $colorQuery);
        $muscleGroups = explode(",", $muscleGroupsQuery);

        foreach ($muscleGroups as $muscleGroup) {
            $muscleGroup = trim($muscleGroup);
            if (empty($muscleGroup)) continue;

            if (!in_array($muscleGroup, self::$availableMuscleGroups)) {
                throw new InvalidArgumentException("Invalid muscle group: {$muscleGroup}");
            }

            $muscleGroupImage = imagecreatefrompng('./resources/images/' . $muscleGroup . '.png');

            // Scale overlay to 800x800
            $scaledMuscleImage = imagecreatetruecolor(800, 800);
            imagealphablending($scaledMuscleImage, false);
            imagesavealpha($scaledMuscleImage, true);
            imagecopyresampled($scaledMuscleImage, $muscleGroupImage, 0, 0, 0, 0, 800, 800, 1920, 1920);

            // Apply color
            $index = imagecolorexact($scaledMuscleImage, 89, 136, 255);
            if ($index !== -1) {
                imagecolorset($scaledMuscleImage, $index, (int)$colorRgb[0], (int)$colorRgb[1], (int)$colorRgb[2]);
            }

            // Merge
            imagealphablending($baseImage, false);
            imagesavealpha($baseImage, true);
            imagecopymerge($baseImage, $scaledMuscleImage, 0, 0, 0, 0, 800, 800, 100);

            imagedestroy($muscleGroupImage);
            imagedestroy($scaledMuscleImage);
        }
    }
}