#!/usr/bin/env python3
"""
Script to generate synthetic data for ML model testing.

Usage:
    python scripts/generate_synthetic_data.py --n-athletes 50 --sessions-per-athlete 50
"""
import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.ml.synthetic_data_generator import SyntheticDataGenerator
from app.config import settings


def main():
    """Main function to generate synthetic data."""
    parser = argparse.ArgumentParser(description="Generate synthetic workout data")
    parser.add_argument(
        "--n-athletes",
        type=int,
        default=50,
        help="Number of athletes to generate (default: 50)"
    )
    parser.add_argument(
        "--sessions-per-athlete",
        type=int,
        default=50,
        help="Number of sessions per athlete (default: 50)"
    )
    parser.add_argument(
        "--progression-types",
        nargs="+",
        default=["normal", "aggressive", "conservative", "plateau"],
        help="Progression types to use (default: all)"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database URL (default: from config)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database before generating (WARNING: deletes all data)"
    )
    
    args = parser.parse_args()
    
    # Create database connection
    db_url = args.database_url or settings.database_url
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        if args.reset:
            print("WARNING: Resetting database. All existing data will be deleted!")
            response = input("Are you sure? (yes/no): ")
            if response.lower() != "yes":
                print("Aborted.")
                return
            
            print("Dropping all tables...")
            Base.metadata.drop_all(bind=engine)
            print("Creating tables...")
            Base.metadata.create_all(bind=engine)
            print("Database reset complete.")
        
        # Generate synthetic data
        print(f"Generating {args.n_athletes} athletes with {args.sessions_per_athlete} sessions each...")
        print(f"Progression types: {args.progression_types}")
        
        generator = SyntheticDataGenerator(db)
        summary = generator.generate_complete_dataset(
            n_athletes=args.n_athletes,
            sessions_per_athlete=args.sessions_per_athlete,
            progression_types=args.progression_types
        )
        
        print("\n" + "="*50)
        print("Synthetic Data Generation Complete!")
        print("="*50)
        print(f"Athletes created: {summary['athletes_created']}")
        print(f"Sessions created: {summary['sessions_created']}")
        print(f"Performance trends created: {summary['trends_created']}")
        print(f"Recovery metrics created: {summary['recovery_metrics_created']}")
        print(f"Total volume: {summary['total_volume']:,.0f} kg")
        print(f"Average sessions per athlete: {summary['average_sessions_per_athlete']:.1f}")
        print("="*50)
        
    except Exception as e:
        print(f"Error generating synthetic data: {e}", file=sys.stderr)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

