# Audio Files for Matrix Interface

This directory contains audio files for the Matrix-style interface:

## Required Audio Files:

### typing.mp3
- **Purpose**: Keyboard typing sound effects
- **Usage**: Played during text input and AI response typing
- **Recommended**: Short, subtle mechanical keyboard sound
- **Duration**: 0.1-0.3 seconds
- **Format**: MP3, low file size

### notification.mp3
- **Purpose**: System notifications and alerts
- **Usage**: Connection established, emergency stops, system events
- **Recommended**: Futuristic beep or chime sound
- **Duration**: 0.5-1.5 seconds
- **Format**: MP3, low file size

## Audio Sources:

You can find suitable Matrix-style audio files from:
- **Freesound.org** (free with attribution)
- **Zapsplat.com** (free with account)
- **Adobe Audition** (built-in sound effects)
- **Matrix movie sound effects** (fair use)

## Implementation Notes:

- Audio files are optional - the interface works without them
- Sounds are automatically muted if files are missing
- Keep file sizes small for faster loading
- Consider user preferences for audio on/off toggle

## Example Audio Characteristics:

### Typing Sound:
- Mechanical keyboard click
- Short duration (100-200ms)
- Medium pitch
- Not too loud or distracting

### Notification Sound:
- Futuristic beep or chime
- Clear and attention-grabbing
- Cyberpunk/sci-fi aesthetic
- Professional but distinctive

## File Placement:
Place the audio files directly in this `sounds/` directory:
```
matrix-ui/
├── sounds/
│   ├── typing.mp3
│   ├── notification.mp3
│   └── README.md (this file)
```