# Lottie Animations - MBTIChatFriend

Three cute character animations created for the MBTI Chat Friend app.

## Files Created

### 1. `happy.json` (4.0 KB)
**Animation**: Bouncing yellow circle with happy face
- **Color**: Golden yellow (#FFD700)
- **Movement**: Vertical bounce with scaling (100% → 110%)
- **Features**:
  - Yellow circle background
  - Two black eyes
  - Curved smile (path stroke)
- **Duration**: 3 seconds (90 frames @ 30fps)
- **Loop**: Continuous

### 2. `love.json` (3.7 KB)
**Animation**: Pulsing pink heart with glow
- **Color**: Hot pink (#FF69B4) with lighter glow effect
- **Movement**: Scale pulse with opacity fade (80% → 100% → 80%)
- **Features**:
  - Pink heart shape (path-based Bezier curves)
  - Glow layer for ambient effect
  - Opacity variation for pulsing effect
- **Duration**: 3 seconds (90 frames @ 30fps)
- **Loop**: Continuous

### 3. `idle.json` (3.9 KB)
**Animation**: Soft breathing/floating circle
- **Color**: Soft pastel blue (#B5C2FF)
- **Movement**: Subtle vertical float (5px) + gentle scale breathing (95% → 102%)
- **Features**:
  - Blue circle background
  - Two small black eyes
  - Relaxed mouth
  - Slow, calming animation
- **Duration**: 3 seconds (90 frames @ 30fps)
- **Loop**: Continuous

## Technical Details

All animations follow the Bodymovin/Lottie JSON format (v5.12.2):
- **Resolution**: 200x200 pixels
- **Framerate**: 30 fps
- **Frame Count**: 90 frames (3 seconds duration)
- **Animation Style**: Looping
- **Shapes Used**: Ellipses (circles) and Paths (smile, heart)

## Usage in Android

```kotlin
// In Compose:
LottieAnimation(
    composition = rememberLottieComposition(R.raw.happy).value,
    modifier = Modifier.size(200.dp),
    iterations = LottieConstants.IterateForever
)
```

## Color Palette

| Animation | Primary Color | RGB | Hex |
|-----------|---------------|-----|-----|
| Happy | Golden Yellow | (255, 215, 0) | #FFD700 |
| Love | Hot Pink | (255, 105, 180) | #FF69B4 |
| Idle | Pastel Blue | (181, 194, 255) | #B5C2FF |

## Animation Characteristics

| Animation | Tone | Use Case | Speed |
|-----------|------|----------|-------|
| Happy | Energetic, bouncy | Success, positive messages | Fast (3s cycle) |
| Love | Warm, emotional | Affection, favorite messages | Medium (3s pulse) |
| Idle | Calm, peaceful | Waiting, neutral state | Slow (3s breath) |

---

Path: `/app/src/main/assets/lottie/`

Created: 2026-02-16
