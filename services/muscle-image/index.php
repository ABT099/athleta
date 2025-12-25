<?php

include('util/Router.php');
include('controllers/MuscleImageController.php');

Router::createRoute('get', '/getMuscleGroups', function() {
    MuscleImageController::getMuscleGroups();
});

Router::createRoute('get', '/getMuscleGroups?', function() {
    MuscleImageController::getMuscleGroups();
});

Router::createRoute('get', '/getBaseImage', function() {
    MuscleImageController::getBaseImage(0);
});

Router::createRoute('get', '/getBaseImage?', function() {
    MuscleImageController::getBaseImage(0);
});

Router::createRouteWithQueryParameters('get', '/getBaseImage', array(
    'transparentBackground' => Router::$PARAMETER_TYPE['number']
),function($transparentBackground) {
    MuscleImageController::getBaseImage($transparentBackground);
});

Router::createRouteWithQueryParameters('get', '/getImage', array(
    'muscleGroups' => Router::$PARAMETER_TYPE['string'],
    'color' => Router::$PARAMETER_TYPE['string'],
    'transparentBackground' => Router::$PARAMETER_TYPE['number']
), function($muscleGroups, $color, $transparentBackground) {
    if ($muscleGroups == null) {
        http_response_code(400);
        exit;
    }
    if ($color == null) {
        MuscleImageController::getMuscleImage($muscleGroups, $transparentBackground);
    } else {
        MuscleImageController::getMuscleImageWithCustomColor($muscleGroups, $color, $transparentBackground);
    }
});

Router::createRouteWithQueryParameters('get', '/getMulticolorImage', array(
    'primaryMuscleGroups' => Router::$PARAMETER_TYPE['string'],
    'secondaryMuscleGroups' => Router::$PARAMETER_TYPE['string'],
    'primaryColor' => Router::$PARAMETER_TYPE['string'],
    'secondaryColor' => Router::$PARAMETER_TYPE['string'],
    'transparentBackground' => Router::$PARAMETER_TYPE['number']
), function($primaryMuscleGroups, $secondaryMuscleGroups, $primaryColor, $secondaryColor, $transparentBackground) {
    if ($primaryMuscleGroups == null || $secondaryMuscleGroups == null || $primaryColor == null || $secondaryColor == null) {
        http_response_code(400);
        exit;
    }
    MuscleImageController::getMuscleImageWithMultiColor($primaryMuscleGroups, $secondaryMuscleGroups, $primaryColor, $secondaryColor, $transparentBackground);
});

Router::createRouteWithQueryParameters('get', '/getIndividualColorImage', array(
    'muscleGroups' => Router::$PARAMETER_TYPE['string'],
    'colors' => Router::$PARAMETER_TYPE['string'],
    'transparentBackground' => Router::$PARAMETER_TYPE['number']
), function ($muscleGroups, $colors, $transparentBackground) {
    if ( $muscleGroups == null || $colors == null) {
        MuscleImageController::getIndividualColorImage("", "", $transparentBackground);
    } else {
        MuscleImageController::getIndividualColorImage($muscleGroups, $colors, $transparentBackground);
    }
});

Router::createRoute('get', '/', function() {
    echo "Welcome to the muscle group image generator api.";
});

Router::createRoute('get', '/test', function() {
    MuscleImageController::testCreateImage();
});

Router::createRoute('get', '/health', function() {
    http_response_code(200);
    header('Content-Type: application/json');
    echo json_encode(['status' => 'healthy', 'service' => 'muscle-image-api']);
});

// POST endpoint for generating and storing images to R2
Router::createRoute('post', '/generateAndStore', function() {
    // Read JSON body
    $json = file_get_contents('php://input');
    $data = json_decode($json, true);
    
    if (!$data) {
        http_response_code(400);
        header('Content-Type: application/json');
        echo json_encode(['error' => 'Invalid JSON']);
        exit;
    }
    
    $workoutDayId = $data['workoutDayId'] ?? null;
    $primaryMuscleGroups = $data['primaryMuscleGroups'] ?? '';
    $secondaryMuscleGroups = $data['secondaryMuscleGroups'] ?? '';
    $primaryColor = $data['primaryColor'] ?? '255,89,94';
    $secondaryColor = $data['secondaryColor'] ?? '138,201,38';
    
    if (!$workoutDayId) {
        http_response_code(400);
        header('Content-Type: application/json');
        echo json_encode(['error' => 'workoutDayId is required']);
        exit;
    }
    
    MuscleImageController::generateAndStoreImage(
        $workoutDayId,
        $primaryMuscleGroups,
        $secondaryMuscleGroups,
        $primaryColor,
        $secondaryColor
    );
});

// Start the Router
Router::run('/');