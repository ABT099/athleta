<?php
/**
 * One-time script to resize base images from 1920x1920 to 800x800
 * Run this script once to create optimized base images
 */

$sourceDir = __DIR__ . '/../resources/images';
$baseImages = ['baseImage.png', 'baseImage_transparent.png'];

foreach ($baseImages as $imageName) {
    $sourcePath = $sourceDir . '/' . $imageName;
    $outputPath = $sourceDir . '/' . str_replace('.png', '_800.png', $imageName);
    
    if (!file_exists($sourcePath)) {
        echo "Warning: {$sourcePath} not found, skipping...\n";
        continue;
    }
    
    // Load source image
    $source = imagecreatefrompng($sourcePath);
    if (!$source) {
        echo "Error: Could not load {$sourcePath}\n";
        continue;
    }
    
    // Get original dimensions
    $width = imagesx($source);
    $height = imagesy($source);
    
    // Create 800x800 canvas
    $resized = imagecreatetruecolor(800, 800);
    imagealphablending($resized, false);
    imagesavealpha($resized, true);
    
    // Resize with high quality
    imagecopyresampled($resized, $source, 0, 0, 0, 0, 800, 800, $width, $height);
    
    // Save resized image
    imagepng($resized, $outputPath);
    
    // Cleanup
    imagedestroy($source);
    imagedestroy($resized);
    
    echo "Created: {$outputPath}\n";
}

echo "Done!\n";

