# Training Science & Implementation Guide

## Overview

This document explains the scientific principles and research backing the AthleteAI progressive overload system.

---

## Table of Contents

1. [Progressive Overload](#progressive-overload)
2. [Gender & Age-Based Adjustments](#gender--age-based-adjustments)
3. [Exercise-Specific Progression](#exercise-specific-progression)
4. [Autoregulated Deloads](#autoregulated-deloads)
5. [Periodization Models](#periodization-models)
6. [RPE Calibration](#rpe-calibration)
7. [Machine Learning Integration](#machine-learning-integration)
8. [Scientific References](#scientific-references)

---

## Progressive Overload

### Principle

Progressive overload is the gradual increase of stress placed on the body during training. It's the fundamental principle for strength and hypertrophy gains.

### Implementation

- **Volume Progression**: Increase sets/reps over time
- **Intensity Progression**: Increase load (weight) over time
- **Frequency Progression**: Increase training frequency
- **Density Progression**: Decrease rest periods

### Experience-Based Rates

| Experience Level | Load Increase/Session | Volume Increase/Week |
|-----------------|---------------------|---------------------|
| Beginner        | 5%                  | 10%                 |
| Intermediate    | 2.5%                | 5%                  |
| Advanced        | 1%                  | 2.5%                |

**References:**
- NSCA Guidelines (2008)
- Schoenfeld et al. (2017): Volume landmarks for hypertrophy

---

## Gender & Age-Based Adjustments

### Gender Differences

#### Women vs Men

**Recovery Capacity:**
- Women recover ~10% faster from volume training
- Less muscle damage from eccentric loading
- Better fatigue resistance in moderate rep ranges

**Peak Performance Years:**
- Women ages 18-35: +5% additional recovery boost
- Hormonal factors (estrogen) enhance recovery

**Implementation:**
```python
GENDER_RECOVERY_MODIFIERS = {
    Gender.MALE: 1.0,    # Baseline
    Gender.FEMALE: 1.1,  # 10% faster recovery
}
```

**References:**
- Kraemer et al. (2001): Gender differences in recovery
- Hunter (2014): Sex differences in muscle recovery
- Sung et al. (2014): Menstrual cycle effects

### Age-Based Progression

#### Age Brackets & Modifiers

| Age Range | Progression Modifier | Rationale |
|-----------|---------------------|-----------|
| 18-25     | 1.15 (115%)         | Peak recovery, optimal protein synthesis |
| 26-35     | 1.0 (100%)          | Baseline performance |
| 36-45     | 0.85 (85%)          | Reduced recovery capacity |
| 46-55     | 0.70 (70%)          | Masters athlete adjustments |
| 56+       | 0.60 (60%)          | Longer recovery needed |

**Physiological Changes with Age:**
- Decreased protein synthesis rates
- Reduced satellite cell activity
- Longer recovery times between sessions
- Increased injury risk with rapid progressions

**References:**
- Schoenfeld et al. (2016): Effects of age on hypertrophy
- Ahtiainen et al. (2016): Training adaptations across age groups

---

## Exercise-Specific Progression

### Compound vs Isolation Exercises

#### Compound Exercises
- **Examples**: Squat, deadlift, bench press, rows
- **Progression Rate**: 1-3% per session
- **Rationale**: Higher CNS fatigue, more technical complexity

#### Isolation Exercises
- **Examples**: Bicep curls, leg extensions, tricep extensions
- **Progression Rate**: 3-6% per session
- **Rationale**: Lower systemic fatigue, simpler movement patterns

### Exercise Familiarity

**New Exercises:**
- First 4-6 weeks: 1% progression regardless of type
- Allows motor pattern learning
- Prevents injury from unfamiliar movements

**Familiarity Score:**
- Starts at 0.0 (completely new)
- Increases by 0.1 per session
- Considered "familiar" at 0.6+

### Double Progression for Hypertrophy

**Concept**: Progress reps first, then weight

**Steps:**
1. **Rep Progression Phase**
   - Start at minimum reps (e.g., 6)
   - Add 1 rep per session
   - Continue until max reps reached (e.g., 12)

2. **Weight Progression Phase**
   - Increase weight by 5%
   - Reset to minimum reps
   - Begin rep progression again

**Example:**
```
Week 1: 100kg × 6 reps × 3 sets
Week 2: 100kg × 7 reps × 3 sets
Week 3: 100kg × 8 reps × 3 sets
...
Week 7: 100kg × 12 reps × 3 sets
Week 8: 105kg × 6 reps × 3 sets (weight increased, reps reset)
```

**References:**
- Krieger (2010): Volume and hypertrophy dose-response
- Schoenfeld (2010): Mechanisms of hypertrophy

---

## Autoregulated Deloads

### Traditional vs Autoregulated

**Traditional Deloads:**
- Fixed every 4 weeks
- Ignores individual recovery capacity
- May be too early or too late

**Autoregulated Deloads:**
- Based on performance and recovery metrics
- Individualized timing
- Prevents overtraining and undertraining

### Deload Triggers

System monitors these indicators:

1. **Performance Drop**
   - ≥10% decrease over last 2 sessions
   - Indicates accumulated fatigue

2. **Readiness Score**
   - <0.5 for 3+ consecutive days
   - Sleep + recovery markers

3. **RPE Spike**
   - RPE increase >1.5 points at same/lower volume
   - Suggests fatigue accumulation

4. **Critical Readiness**
   - Current readiness <0.4
   - Immediate concern

### Deload Protocol

When triggered:
- **Volume**: Reduce to 50%
- **Intensity**: Reduce to 85-90%
- **Duration**: Typically 1 week

**References:**
- Zourdos et al. (2016): RPE-based autoregulation
- Mann et al. (2010): Autoregulatory progressive resistance

---

## Periodization Models

### 1. Linear Periodization

**Structure:**
- Start with high volume, low intensity
- Gradually increase intensity, decrease volume
- Classic beginner approach

**Best For:**
- Beginners
- Athletes with <2 sessions/week

### 2. Daily Undulating Periodization (DUP)

**Structure:**
Vary volume and intensity within the same week

**Example Week:**
- **Day 1 (Monday)**: High Volume Day
  - 10-12 reps @ 70% 1RM
  - 20% more sets than baseline
  
- **Day 2 (Wednesday)**: Moderate Day
  - 6-8 reps @ 80% 1RM
  - Normal set count
  
- **Day 3 (Friday)**: High Intensity Day
  - 3-5 reps @ 90% 1RM
  - 30% fewer sets

**Advantages:**
- Better for intermediate/advanced athletes
- More frequent exposure to different rep ranges
- Reduces monotony

**References:**
- Rhea et al. (2002): DUP produces greater strength gains than linear
- Zourdos et al. (2016): DUP with autoregulation

### 3. Block Periodization

**Structure:**
Sequential blocks focusing on specific adaptations

**Block 1: Accumulation (3-4 weeks)**
- Focus: High volume
- Volume: 120% of baseline
- Intensity: 75% of peak
- Goal: Build work capacity

**Block 2: Intensification (2-3 weeks)**
- Focus: Strength building
- Volume: 85% of baseline
- Intensity: 110% of baseline
- Goal: Convert volume to strength

**Block 3: Realization (1-2 weeks)**
- Focus: Peak performance
- Volume: 60% of baseline
- Intensity: 115% of baseline
- Goal: Demonstrate maximum strength

**References:**
- Issurin (2010): Block periodization for sports training
- Kiely (2012): Periodization theory

---

## RPE Calibration

### The RPE-RIR Relationship

**RPE (Rate of Perceived Exertion)**: How hard the set feels (1-10 scale)

**RIR (Reps in Reserve)**: How many more reps you could do

**Standard Conversion:**
| RPE  | RIR |
|------|-----|
| 10   | 0   |
| 9.5  | 0   |
| 9    | 1   |
| 8.5  | 1   |
| 8    | 2   |
| 7.5  | 2   |
| 7    | 3   |

### Individual Calibration

**Problem**: Athletes vary in RPE perception accuracy

**Solution**: Track actual vs reported difficulty

**Calibration Process:**

1. **Data Collection**
   - Athlete reports RPE
   - Track actual reps achieved
   - Record proximity to failure

2. **Pattern Recognition**
   - Calculate athlete's RPE bias
   - Some underestimate difficulty (report lower RPE)
   - Some overestimate difficulty (report higher RPE)

3. **Adjustment**
   - Apply calibration factor
   - Factor >1.0 = underestimates
   - Factor <1.0 = overestimates

### Hybrid Rule-Based + ML Approach

**Phase 1: Rule-Based (0-30 sessions)**
- Use standard RPE-to-RIR conversion
- Track athlete's accuracy
- Calculate calibration factor

**Phase 2: ML Enhancement (30+ sessions)**
- Train GradientBoostingRegressor
- Features: RPE, weight, reps, interactions
- Target: Actual RIR
- Combine ML (70%) + Rules (30%)

**References:**
- Zourdos et al. (2016): RPE accuracy and autoregulation
- Helms et al. (2016): Application of RPE-based training

---

## Machine Learning Integration

### Hybrid Approach Philosophy

**Why Hybrid?**
- ML learns individual patterns
- Rules provide safety guardrails
- Best of both worlds

### Workout Parameter Prediction

**Model**: RandomForestRegressor

**Features** (40+):
- Athlete demographics (age, gender, experience)
- Recent performance (last 5 sessions)
- Recovery metrics (sleep, soreness, stress)
- Training load (ACWR, monotony)
- Volume/intensity trends

**Targets**:
- Volume multiplier (0.7 - 1.3)
- Intensity multiplier (0.8 - 1.15)

**Training Requirements**:
- Minimum: 20 completed sessions
- Optimal: 50+ sessions
- Retraining: Every 50 sessions or 90 days

**Prediction Strategy**:

| ML Confidence | Weighting | Reasoning |
|---------------|-----------|-----------|
| ≥0.7 (High)   | 80% ML, 20% Rules | Trust ML heavily |
| 0.5-0.7 (Med) | 50% ML, 50% Rules | Balanced approach |
| <0.5 (Low)    | 100% Rules | Safety first |

### RPE Calibration ML

**Model**: GradientBoostingRegressor

**Features**:
- Reported RPE
- Weight used
- Reps completed
- RPE × Reps (interaction)

**Target**: Actual RIR

**Implementation**:
```python
# Weighted prediction
if ml_weight > 0:
    hybrid_rir = (ml_rir * ml_weight) + (rule_rir * (1 - ml_weight))
```

**ML Weight Progression**:
- 30 samples: 0% ML (pure rules)
- 40 samples: 35% ML, 65% rules
- 50+ samples: 70% ML, 30% rules

### Model Interpretability

**Feature Importance**: Track which factors matter most

**Example Rankings**:
1. Recent readiness scores (35%)
2. Volume trend (20%)
3. Age/experience (15%)
4. Recovery metrics (15%)
5. RPE trends (10%)
6. Other (5%)

**References:**
- ML in sports: Claudino et al. (2019)
- Predictive modeling: Carey et al. (2018)

---

## Scientific References

### Progressive Overload & Training Principles
1. **NSCA (2008)**: Essentials of Strength Training and Conditioning
2. **Schoenfeld et al. (2017)**: "Dose-response relationship between weekly resistance training volume and increases in muscle mass"
3. **Krieger (2010)**: "Single vs multiple sets for hypertrophy"

### Gender & Age Differences
4. **Kraemer et al. (2001)**: "Gender differences in recovery from resistance training"
5. **Hunter (2014)**: "Sex differences in human fatigability"
6. **Sung et al. (2014)**: "Effects of menstrual cycle on training adaptation"
7. **Schoenfeld et al. (2016)**: "Effects of resistance training frequency"
8. **Ahtiainen et al. (2016)**: "Heterogeneity in resistance training-induced muscle strength"

### RPE & Autoregulation
9. **Zourdos et al. (2016)**: "Modified RPE scale for resistance exercise"
10. **Mann et al. (2010)**: "Effect of autoregulatory progressive resistance"
11. **Helms et al. (2016)**: "Application of the repetitions in reserve-based RPE scale"

### Periodization
12. **Rhea et al. (2002)**: "A comparison of linear and daily undulating periodization"
13. **Issurin (2010)**: "New horizons for the methodology of sports training"
14. **Kiely (2012)**: "Periodization paradigms in the 21st century"

### Injury Prevention
15. **Gabbett (2016)**: "The training-injury prevention paradox"
16. **Banister et al. (1991)**: "Modeling human performance in running"

### Machine Learning in Sports
17. **Claudino et al. (2019)**: "Current approaches to the use of AI for injury risk assessment"
18. **Carey et al. (2018)**: "Predictive modelling of training loads and injury in Australian football"

---

## Implementation Summary

### What Makes This System Effective

1. **Individualized**: Adapts to each athlete's unique characteristics
2. **Evidence-Based**: Grounded in peer-reviewed research
3. **Autoregulated**: Adjusts based on performance and recovery
4. **Safety-First**: Injury prevention built into every decision
5. **Hybrid Intelligence**: Combines rules + ML for best results

### Key Innovations

- **Gender-specific recovery modifiers** (women +10%)
- **Age-based progression adjustments** (6 age brackets)
- **Exercise-specific rates** (compound vs isolation)
- **Performance-based deloads** (not time-based)
- **Hybrid ML predictions** (confidence-based weighting)
- **Individual RPE calibration** (learns your patterns)
- **Multiple periodization models** (DUP, Block, Linear)

---

*Last Updated: November 8, 2025*

