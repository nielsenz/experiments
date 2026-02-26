# Claude Code Best Practices

This file documents best practices for working with the summarize-podcast tool and related audio/video processing.

## Whisper.cpp Best Practices

### Model Selection

| Model | Size | Use Case |
|-------|------|----------|
| `ggml-tiny.bin` | 75MB | Quick tests, low-quality audio |
| `ggml-base.bin` | 142MB | Short clips, clear audio |
| `ggml-small.bin` | 466MB | General use, good accuracy |
| `ggml-medium.bin` | 1.5GB | **Recommended** - best balance |
| `ggml-large-v3.bin` | 3GB | Maximum accuracy, slow |

### Performance Tips

1. **Use Apple Silicon GPU**: whisper.cpp automatically uses Metal on M-series chips
2. **Batch processing**: Process multiple files sequentially to avoid memory pressure
3. **Audio quality**: Higher bitrate source audio = better transcription accuracy

### Common whisper-cli Flags

```bash
# Basic transcription to text file
whisper-cli -m MODEL_PATH -f audio.mp3 -otxt -of output_name

# Useful flags:
# -l en          Force English language detection
# -t 4           Use 4 threads (default: 4)
# -p 1           Use 1 processor
# --no-timestamps  Omit timestamps from output
```

### Transcription Quality

For best results:
- Use audio with minimal background noise
- Podcasts with clear speech transcribe well
- Music/sound effects may cause hallucinations
- Consider pre-processing audio (normalize volume, remove intro music)

## Summarize CLI Best Practices

### Configuration

Store config at `~/.summarize/config.json`:

```json
{
  "cli": {
    "enabled": ["gemini"]
  }
}
```

**Why Gemini CLI?**
- ~4s faster than cloud API calls
- No rate limiting
- Free tier available

### Effective Prompts

**Extraction prompts** (pull specific info):
```bash
--prompt "Extract all betting picks with specific lines and odds"
--prompt "List all action items and deadlines mentioned"
--prompt "Summarize the key arguments for and against each position"
```

**Summary prompts** (condense content):
```bash
--prompt "Provide a brief executive summary in 3 bullet points"
--prompt "Summarize for someone with 2 minutes to read"
```

**Analysis prompts** (derive insights):
```bash
--prompt "Identify the main themes and how they connect"
--prompt "What are the strongest and weakest arguments presented?"
```

### Length Options

| Flag | Output Length | Use Case |
|------|---------------|----------|
| `--length short` | ~500 chars | Quick overview |
| `--length medium` | ~1500 chars | Standard summary |
| `--length long` | ~3000 chars | Detailed summary |
| `--length xl` | ~6000 chars | Comprehensive (default for this tool) |
| `--length xxl` | ~12000 chars | Very detailed |

### Working with Long Content

For podcasts over 1 hour:
1. Transcription may produce 15,000+ words
2. Use `--length xl` or `xxl` to capture more detail
3. Consider chunking very long content manually

## Workflow Patterns

### Pattern 1: Quick YouTube Summary

```bash
# YouTube videos often have auto-generated subtitles
summarize-podcast "https://youtube.com/watch?v=VIDEO_ID"
```
- Fast (~30s) because it uses existing subtitles
- May have transcription errors from auto-captions

### Pattern 2: High-Quality Podcast Summary

```bash
# RSS feeds require local transcription
summarize-podcast "https://feeds.example.com/podcast.xml"
```
- Slower (~8 min/hour) but more accurate
- Uses local Whisper model

### Pattern 3: Batch Processing

```bash
# Process multiple episodes
summarize-podcast "https://feeds.example.com/podcast.xml" 5

# Or loop with custom prompts
for url in "${EPISODE_URLS[@]}"; do
    summarize-podcast --prompt "Extract key insights" "$url" >> summaries.md
done
```

### Pattern 4: Research Workflow

```bash
# Step 1: Get transcript only
summarize-podcast --transcript "URL" > transcript.txt

# Step 2: Review and identify focus areas
# Step 3: Re-summarize with targeted prompt
summarize transcript.txt --prompt "Focus on X topic"
```

## Common Issues & Solutions

### Issue: "Unsupported file type: audio/mpeg"

**Cause**: The `summarize` CLI doesn't handle audio directly.

**Solution**: This tool already handles this by:
1. Downloading audio separately
2. Running whisper-cli locally
3. Passing text transcript to summarize

### Issue: Slow transcription

**Solutions**:
- Use a smaller model (`ggml-small.bin` vs `ggml-medium.bin`)
- Ensure you're on Apple Silicon (uses GPU)
- Close other GPU-intensive apps

### Issue: Poor transcription quality

**Solutions**:
- Use a larger model (`ggml-medium.bin` or `ggml-large-v3.bin`)
- Check if source audio has music/noise
- Try forcing English: add `-l en` flag to whisper-cli

### Issue: YouTube download fails

**Solutions**:
```bash
# Update yt-dlp (YouTube changes frequently)
brew upgrade yt-dlp

# Or use pip
pip install -U yt-dlp
```

## Finding Podcast RSS Feeds

Most podcasts publish RSS feeds. To find them:

1. **Apple Podcasts**: Search podcast on Apple Podcasts web, the feed is often linked
2. **Podcast websites**: Look for RSS icon or "Subscribe" links
3. **getrssfeed.com**: Enter Apple Podcasts URL to extract RSS feed
4. **ListenNotes**: Search for podcast, RSS feed is listed on the page

Common feed patterns:
- `https://feeds.simplecast.com/XXXXX`
- `https://anchor.fm/s/XXXXX/podcast/rss`
- `https://feeds.megaphone.fm/XXXXX`
- `https://rss.art19.com/XXXXX`

## Example: Sports Betting Podcast Workflow

### Tested Podcasts & Feeds

| Podcast | RSS Feed | YouTube | Content |
|---------|----------|---------|---------|
| Deep Dive Gambling | `https://feeds.simplecast.com/4YRRRgQN` | - | Game picks, awards, props |
| Forward Progress | `https://feeds.megaphone.fm/HAMMR4647969418` | `UCnpHpDsquK4-cZBNZd_Km8A` | RSS: Best bets, YouTube: Props/teasers |
| Bet the Process | `https://feeds.soundcloud.com/users/soundcloud:users:330500902/sounds.rss` | - | Market analysis, best bets (varies by episode) |

### Optimized Prompts (Tested)

**For game picks (spreads/totals):**
```bash
--prompt "Extract all NFL Week 18 game betting picks. Focus on: spreads, totals, and money lines. Include specific lines mentioned and reasoning. Format as a clear list organized by game."
```

**For player props:**
```bash
--prompt "Extract all NFL Week 18 betting picks and prop bets. Focus on specific player props, game picks, and any strong recommendations. Format as a clear list of actionable bets with the specific lines/odds mentioned."
```

**For awards markets:**
```bash
--prompt "Extract all NFL awards betting picks and recommendations. Focus on: MVP, Offensive/Defensive Player of the Year, Rookie of the Year, Coach of the Year. Include odds mentioned and opinions on value."
```

**For teasers:**
```bash
--prompt "Extract all NFL Week 18 teaser bets. Focus on specific teaser legs, lines, and reasoning. Format as a clear list of recommended teaser combinations."
```

### Complete Weekly Workflow

```bash
# 1. Define prompts
GAME_PROMPT="Extract all game betting picks (spreads, totals, money lines) with specific lines and reasoning."
PROP_PROMPT="Extract all player props with specific lines and odds mentioned."

# 2. Deep Dive Gambling - full coverage
summarize-podcast --prompt "$GAME_PROMPT" "https://feeds.simplecast.com/4YRRRgQN" 2

# 3. Forward Progress RSS - best bets (game picks)
summarize-podcast --prompt "$GAME_PROMPT" "https://feeds.megaphone.fm/HAMMR4647969418"

# 4. Forward Progress YouTube - props & teasers
summarize-podcast --prompt "$PROP_PROMPT" "https://www.youtube.com/channel/UCnpHpDsquK4-cZBNZd_Km8A" 2
```

### Key Learnings

1. **RSS vs YouTube content differs**: Forward Progress puts detailed game analysis on RSS but props/teasers on YouTube. Always check both.

2. **Episode selection matters**: Look at episode titles first:
   - "Best Bets" / "Early Best Bets" = game picks (spreads/totals)
   - "Props" / "Prop Bets" = player props
   - "Teaser Bets" = teaser combinations
   - "Pizza Buffet" = live show with all picks

3. **Transcription time**: ~6-8 minutes per hour of audio on M3 Pro. A 45-min podcast takes ~5-6 minutes to transcribe.

4. **YouTube is faster**: If a video has auto-captions, it's ~30 seconds vs 6+ minutes for audio transcription. Check YouTube first.

5. **Summarization quality**: Gemini CLI produces well-formatted markdown tables automatically when the prompt asks for structured output.

### Sample Output Format

When using the game picks prompt, expect output like:

```
| Game | Pick | Confidence | Reasoning |
|------|------|------------|-----------|
| Panthers @ Bucs | Panthers +3 | Triple Hammer | TB bottom-8 team, Baker injured |
| Seahawks @ 49ers | Seahawks -1.5 | Single Hammer | SEA #1 run D |
```

### Combining Multiple Sources

To find consensus plays, run multiple podcasts and look for agreement:

```bash
# Create a combined summary
{
  echo "## Deep Dive Gambling"
  summarize-podcast --prompt "$GAME_PROMPT" "https://feeds.simplecast.com/4YRRRgQN"

  echo "## Forward Progress"
  summarize-podcast --prompt "$GAME_PROMPT" "https://feeds.megaphone.fm/HAMMR4647969418"
} > weekly_picks.md
```

Consensus plays (mentioned by multiple sources) tend to have higher confidence.

## Lessons Learned (Wildcard Week Run)

1. **Source selection matters**: For Wild Card week, the most relevant Forward Progress RSS episode was "NFL Wildcard Week Best Bets and Predictions"; Deep Dive's relevant shows were "Monday Morning Markets: Wildcard Weekend" and "Wednesday Walk-Thru: NFL Wildcard Weekend".
2. **YouTube IDs should be verified**: Props and teaser content can be older slates; confirm the upload date or title context before running. Examples used: `vVt1Ap9W5os` (Wild Card props) and `u8DFf88PR4c` (teaser bets).
3. **Transcript pipeline gotcha**: `yt-dlp` logs can pollute stdout if not redirected, which breaks the script's transcript path handling. Suppress stdout from `yt-dlp` and `whisper-cli` to keep outputs clean.
4. **Prompt reuse works**: "Extract all wild card best bets with lines/odds" produced structured output across RSS and YouTube, but prop-focused shows will return player markets rather than game sides/totals.
