"""
Prescription generation API endpoints.
"""
from fastapi import APIRouter, HTTPException
from app.schemas.prescription import (
    PrescriptionRequest,
    PrescriptionResponse,
    BatchPrescriptionRequest,
    BatchPrescriptionResponse,
)
from app.services.prescription_generator import PrescriptionGeneratorService

router = APIRouter()


@router.post("/prescriptions/generate", response_model=PrescriptionResponse)
def generate_prescription(request: PrescriptionRequest) -> PrescriptionResponse:
    """
    Generate target RPE, RIR, and rest period for a single exercise.
    
    Uses scientifically-validated rules:
    - CNS Tax Rule: Compounds capped at RPE 9.0
    - Inverse RPE/RIR Law: RIR = 10 - RPE
    - Hybrid Logic: Compounds follow strength, isolations follow hypertrophy
    - Phase-aware: Adjusts based on accumulation/intensification/realization/deload
    - Microcycle progression: Week-in-phase progressive overload
    """
    try:
        service = PrescriptionGeneratorService()
        result = service.generate_prescription(
            intensity_category=request.intensity_category,
            training_type=request.training_type,
            training_phase=request.training_phase,
            week_in_phase=request.week_in_phase,
            is_primary=request.is_primary
        )
        return PrescriptionResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate prescription: {str(e)}")


@router.post("/prescriptions/generate-batch", response_model=BatchPrescriptionResponse)
def generate_batch_prescriptions(request: BatchPrescriptionRequest) -> BatchPrescriptionResponse:
    """
    Generate prescriptions for multiple exercises at once.
    
    Useful for initial workout plan creation where multiple exercises need prescriptions.
    """
    try:
        service = PrescriptionGeneratorService()
        prescriptions = []
        
        for req in request.prescriptions:
            result = service.generate_prescription(
                intensity_category=req.intensity_category,
                training_type=req.training_type,
                training_phase=req.training_phase,
                week_in_phase=req.week_in_phase,
                is_primary=req.is_primary
            )
            prescriptions.append(PrescriptionResponse(**result))
        
        return BatchPrescriptionResponse(prescriptions=prescriptions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate batch prescriptions: {str(e)}")


