# Summarize Podcast Tool

A command-line tool to summarize podcasts and YouTube videos using local Whisper transcription and the `summarize` CLI.

## Features

- Summarize podcast episodes from RSS feeds
- Summarize YouTube videos (single or from channels/playlists)
- Local audio transcription using whisper.cpp (no cloud API needed)
- Custom prompts for targeted summaries (e.g., "Extract betting picks")
- Transcript-only mode for raw output

## Prerequisites

### Required Tools

```bash
# Install summarize CLI
npm install -g @steipete/summarize

# Install whisper.cpp for local transcription
brew install whisper-cpp

# Install yt-dlp for YouTube support
brew install yt-dlp
```

### Whisper Model Setup

Download a Whisper model (one-time setup):

```bash
# Create models directory
mkdir -p ~/.local/share/whisper

# Download medium model (~1.5GB, good balance of speed/quality)
curl -L "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin" \
  -o ~/.local/share/whisper/ggml-medium.bin
```

Available models (speed vs accuracy tradeoff):
- `ggml-tiny.bin` (~75MB) - Fastest, lower accuracy
- `ggml-base.bin` (~142MB) - Fast, decent accuracy
- `ggml-small.bin` (~466MB) - Balanced
- `ggml-medium.bin` (~1.5GB) - Recommended
- `ggml-large-v3.bin` (~3GB) - Best accuracy, slowest

### Environment Setup

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
export SUMMARIZE_WHISPER_CPP_MODEL_PATH="$HOME/.local/share/whisper/ggml-medium.bin"
```

## Installation

```bash
# Clone or copy the script
chmod +x summarize-podcast

# Optionally add to PATH
ln -s "$(pwd)/summarize-podcast" /opt/homebrew/bin/
```

## Usage

### Basic Usage

```bash
# Summarize latest podcast episode from RSS feed
summarize-podcast "https://feeds.simplecast.com/4YRRRgQN"

# Summarize last 3 episodes
summarize-podcast "https://feeds.simplecast.com/4YRRRgQN" 3

# Summarize a YouTube video
summarize-podcast "https://www.youtube.com/watch?v=VIDEO_ID"

# Summarize latest 2 videos from a YouTube channel
summarize-podcast "https://www.youtube.com/channel/UCnpHpDsquK4-cZBNZd_Km8A" 2
```

### Custom Prompts

```bash
# Extract specific information
summarize-podcast --prompt "Extract all betting picks and recommendations" \
  "https://feeds.simplecast.com/4YRRRgQN"

# Focus on action items
summarize-podcast --prompt "List key takeaways and action items" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Real-World Examples

```bash
# Deep Dive Gambling Podcast (NFL picks)
summarize-podcast "https://feeds.simplecast.com/4YRRRgQN" 2

# Forward Progress Best Bets (game picks - RSS has more content than YouTube)
summarize-podcast "https://feeds.megaphone.fm/HAMMR4647969418"

# Forward Progress YouTube (props & teasers)
summarize-podcast "https://www.youtube.com/channel/UCnpHpDsquK4-cZBNZd_Km8A" 3
```

**Note**: Some podcasts split content between YouTube and RSS. Forward Progress puts game picks on the RSS feed but props/teasers on YouTube. Check both sources for complete coverage.

### Transcript Only

```bash
# Output raw transcript without summarization
summarize-podcast --transcript "https://www.youtube.com/watch?v=VIDEO_ID"
```

## How It Works

1. **URL Detection**: Automatically detects RSS feeds vs YouTube URLs
2. **Content Retrieval**:
   - YouTube: Downloads auto-generated subtitles (fast) or falls back to audio transcription
   - RSS: Downloads audio file from feed enclosure
3. **Transcription**: Uses local whisper.cpp for audio-to-text (runs on Apple Silicon GPU)
4. **Summarization**: Passes transcript to `summarize` CLI with optional custom prompt

## Performance

On Apple Silicon (M3 Pro):
- YouTube with subtitles: ~30 seconds
- Podcast transcription: ~8 minutes per hour of audio
- Summarization: ~20-30 seconds

## Summarize CLI Configuration

The tool uses the `summarize` CLI under the hood. Configure it at `~/.summarize/config.json`:

```json
{
  "cli": {
    "enabled": ["gemini"]
  }
}
```

This enables the Gemini CLI for summarization (recommended for lowest latency).

## Troubleshooting

### "Unsupported file type: audio/mpeg"

The `summarize` CLI doesn't directly support audio files. This tool works around this by:
1. Downloading audio separately
2. Transcribing with local whisper.cpp
3. Passing the text transcript to summarize

### Whisper model not found

Ensure the model path is set correctly:
```bash
export SUMMARIZE_WHISPER_CPP_MODEL_PATH="$HOME/.local/share/whisper/ggml-medium.bin"
ls -la "$SUMMARIZE_WHISPER_CPP_MODEL_PATH"  # Verify file exists
```

### YouTube download fails

Update yt-dlp:
```bash
brew upgrade yt-dlp
```

## License

MIT
