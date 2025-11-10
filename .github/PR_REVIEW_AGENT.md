# AI Documentation Review Agent

An AI-powered GitHub Action that automatically reviews documentation pull requests using Claude API.

## Overview

This agent reviews documentation changes in pull requests and provides inline feedback on:

- **Grammar and Spelling** (American English)
- **Style Guide Adherence** (Google Developer Documentation Style Guide)
- **MDX/Mintlify Syntax**
- **Frontmatter Completeness**
- **Code Block Formatting** (language tags, formatting)
- **Internal Link Formats**
- **Image Alt Text**

## Key Features

- ✅ **Scoped Reviews**: Only reviews changed lines, not pre-existing content
- 🎯 **Inline Comments**: Posts comments directly on specific lines
- 📊 **Severity Levels**: Classifies issues as critical, major, or minor
- 🧠 **Learning System**: Tracks accepted/ignored suggestions to improve over time
- 🚫 **Smart Filtering**: Excludes auto-generated reference docs
- ⚙️ **Configurable**: Customize review rules and exclusions

## Setup

### 1. Add API Key

Add your Anthropic API key as a GitHub secret:

1. Go to your repository Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `ANTHROPIC_API_KEY`
4. Value: Your Anthropic API key (starts with `sk-ant-...`)

### 2. Enable the Workflow

The workflow is automatically enabled once the files are merged to your main branch. It will run on every pull request that modifies `.md` or `.mdx` files.

## Usage

### Automatic Reviews

The agent automatically runs when:
- A pull request is opened
- New commits are pushed to an existing PR
- A PR is reopened

### Review Output

The agent provides two types of feedback:

1. **Inline Comments**: Posted on specific lines with issues
   - Includes severity level (🚨 Critical, ⚠️ Major, ℹ️ Minor)
   - Describes the issue
   - Suggests a fix

2. **Summary Comment**: Posted as a PR comment
   - Overview of all issues found
   - Breakdown by file
   - Count by severity level

### Example Review Comment

```
⚠️ **MAJOR** - style

Avoid using first-person voice. The style guide recommends second-person voice ("you") for user-facing documentation.

**Suggestion:**
Change "We recommend using..." to "You can use..." or "Use..."

---
AI Documentation Review | [Severity: major]
```

## Configuration

### Review Rules

Edit `.github/pr-review-config.json` to customize:

```json
{
  "enabled_checks": [
    "grammar",
    "spelling",
    "style_guide",
    "mdx_syntax",
    "frontmatter",
    "code_blocks",
    "internal_links"
  ],
  "exclude_patterns": [
    "**/reference/**",
    "**/node_modules/**"
  ],
  "max_issues_per_file": 20,
  "severity_threshold": "minor"
}
```

### Exclude Patterns

To exclude additional paths from review, add them to `exclude_patterns` in the config file:

```json
{
  "exclude_patterns": [
    "**/reference/**",
    "**/generated/**",
    "**/vendor/**"
  ]
}
```

### Custom Rules

You can define custom style rules in the config:

```json
{
  "custom_rules": {
    "frontmatter_required_fields": ["title", "description"],
    "heading_case": "sentence-case",
    "voice": "second-person",
    "language_variant": "american-english"
  }
}
```

## Learning System

The agent tracks feedback to improve over time:

### Feedback Data

Stored in `.github/pr-review-feedback.json`:
- Total reviews conducted
- Accepted suggestion patterns
- Ignored suggestion patterns
- Issue statistics by category and severity

### How It Learns

1. **Accepted Suggestions**: When you commit changes that address a suggestion
2. **Ignored Suggestions**: When you dismiss or ignore a comment
3. **Pattern Recognition**: Over time, the agent recognizes patterns in what's accepted vs. ignored

The learning data is automatically updated after each review and used to refine future reviews.

## Troubleshooting

### Agent Not Running

Check:
- The PR modifies `.md` or `.mdx` files
- Files are not in excluded paths (`**/reference/**`)
- GitHub Actions are enabled for your repository
- `ANTHROPIC_API_KEY` secret is set correctly

### API Rate Limits

If you encounter rate limit issues:
- Consider reducing `max_issues_per_file` in config
- Add delays between API calls (modify the script)
- Upgrade your Anthropic API plan

### False Positives

If the agent frequently flags incorrect issues:
1. Review the suggestions and provide feedback by resolving/dismissing comments
2. The learning system will adapt over time
3. Adjust rules in `.github/pr-review-config.json`
4. Consider updating the review prompt in `.github/scripts/pr_review_agent.py`

## Manual Execution

To test the agent locally:

```bash
# Set environment variables
export GITHUB_TOKEN="your-github-token"
export ANTHROPIC_API_KEY="your-anthropic-key"
export PR_NUMBER="123"
export REPO_NAME="owner/repo"
export BASE_SHA="base-commit-sha"
export HEAD_SHA="head-commit-sha"

# Run the agent
uv run python .github/scripts/pr_review_agent.py
```

## Architecture

### Components

1. **Workflow** (`.github/workflows/pr-review.yml`)
   - Triggers on PR events
   - Sets up Python environment
   - Runs the review script

2. **Review Script** (`.github/scripts/pr_review_agent.py`)
   - Fetches PR changes
   - Filters files to review
   - Calls Claude API
   - Posts GitHub comments

3. **Configuration** (`.github/pr-review-config.json`)
   - Review rules and settings
   - File exclusions
   - Custom style preferences

4. **Feedback Data** (`.github/pr-review-feedback.json`)
   - Learning system data
   - Statistics and patterns

### Review Process

```
PR Event → GitHub Action
    ↓
Fetch Changed Files
    ↓
Filter (exclude reference docs, non-markdown)
    ↓
For each file:
    - Get diff
    - Send to Claude API
    - Parse response
    - Post inline comments
    ↓
Post summary comment
    ↓
Update learning data
```

## Customization

### Modify Review Prompt

Edit the `_get_review_prompt()` method in `.github/scripts/pr_review_agent.py` to:
- Add new check types
- Change emphasis areas
- Adjust tone/style
- Include project-specific guidelines

### Change Model

To use a different Claude model, update the model name in `_review_file_with_claude()`:

```python
model="claude-sonnet-4-5-20250929",  # Current model
# or
model="claude-opus-4-20250514",      # For more detailed reviews
```

## Cost Estimation

Cost depends on:
- Number of PRs
- Size of documentation changes
- Model used (Sonnet 4.5 is recommended for balance of quality/cost)

Typical costs:
- Small PR (1-2 files, <500 lines): $0.01 - $0.05
- Medium PR (3-5 files, 500-2000 lines): $0.05 - $0.20
- Large PR (5+ files, 2000+ lines): $0.20 - $0.50

## Support

For issues or questions:
- Open an issue in the repository
- Check GitHub Actions logs for error details
- Review the feedback data for insights

## Best Practices

1. **Review Agent Suggestions**: Don't blindly accept all suggestions
2. **Provide Feedback**: Resolve helpful comments, dismiss incorrect ones
3. **Adjust Configuration**: Tune rules based on your team's needs
4. **Monitor Costs**: Track API usage in Anthropic dashboard
5. **Update Regularly**: Keep the agent script and dependencies updated
