#!/usr/bin/env python3
"""AI-powered PR review agent for documentation.

This script reviews documentation changes in PRs using Claude API.
It focuses on style guide adherence, grammar, syntax, and best practices.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import anthropic
from github import Github
from github.PullRequest import PullRequest


class PRReviewAgent:
    """AI-powered documentation review agent."""

    def __init__(self) -> None:
        """Initialize the review agent with API clients and configuration."""
        self.anthropic_client = anthropic.Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"]
        )
        self.github_client = Github(os.environ["GITHUB_TOKEN"])
        self.repo = self.github_client.get_repo(os.environ["REPO_NAME"])
        self.pr_number = int(os.environ["PR_NUMBER"])
        self.pr = self.repo.get_pull(self.pr_number)
        self.base_sha = os.environ["BASE_SHA"]
        self.head_sha = os.environ["HEAD_SHA"]

        # Load configuration
        self.config = self._load_config()
        self.feedback_data = self._load_feedback_data()

    def _load_config(self) -> dict[str, Any]:
        """Load review configuration from file."""
        config_path = Path(".github/pr-review-config.json")
        if config_path.exists():
            with config_path.open() as f:
                return json.load(f)
        return self._get_default_config()

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration."""
        return {
            "enabled_checks": [
                "grammar",
                "spelling",
                "style_guide",
                "mdx_syntax",
                "frontmatter",
                "code_blocks",
                "internal_links",
            ],
            "exclude_patterns": ["**/reference/**", "**/node_modules/**"],
            "max_issues_per_file": 20,
        }

    def _load_feedback_data(self) -> dict[str, Any]:
        """Load feedback tracking data."""
        feedback_path = Path(".github/pr-review-feedback.json")
        if feedback_path.exists():
            with feedback_path.open() as f:
                return json.load(f)
        return {"accepted_patterns": [], "ignored_patterns": [], "total_reviews": 0}

    def _save_feedback_data(self) -> None:
        """Save feedback tracking data."""
        feedback_path = Path(".github/pr-review-feedback.json")
        with feedback_path.open("w") as f:
            json.dump(self.feedback_data, f, indent=2)

    def _should_review_file(self, filepath: str) -> bool:
        """Determine if a file should be reviewed."""
        # Must be a markdown file
        if not (filepath.endswith(".md") or filepath.endswith(".mdx")):
            return False

        # Check exclude patterns
        for pattern in self.config["exclude_patterns"]:
            pattern_re = pattern.replace("**", ".*").replace("*", "[^/]*")
            if re.match(pattern_re, filepath):
                return False

        return True

    def _get_review_prompt(self, filepath: str, content: str, diff: str) -> str:
        """Generate the review prompt for Claude."""
        return f"""You are an expert documentation reviewer for the LangChain documentation.
Your task is to review ONLY the changes made in this file, not the entire file.

## Context
File: {filepath}
This is documentation written in MDX format for the Mintlify platform.

## Style Guide
Follow the Google Developer Documentation Style Guide (https://developers.google.com/style).

## Key Review Areas
1. **Grammar and Spelling**: Check for grammatical errors and spelling mistakes (American English)
2. **Style Guide Adherence**:
   - Use second-person voice ("you")
   - Use sentence-case for headings
   - Clear, concise language
   - Prerequisites at start of procedural content
3. **MDX/Mintlify Syntax**: Proper MDX syntax and Mintlify component usage
4. **Frontmatter**: Required fields: title (clear, descriptive, concise) and description (concise summary)
5. **Code Blocks**:
   - All code blocks MUST have language tags
   - Code blocks should be properly formatted
   - DO NOT test or validate the code itself - only check formatting
6. **Internal Links**: Use root-relative paths (e.g., `/path/to/page`), not absolute URLs
7. **Alt Text**: All images must have descriptive alt text

## Special Requirements
- Custom language fences: `:::python` and `:::js` are valid syntax
- DO NOT review auto-generated reference docs (should be excluded already)
- DO NOT comment on code snippet functionality - only formatting
- DO NOT require localization in links (/python/ or /javascript/ prefixes)

## Diff of Changes
{diff}

## Full File Content (for context)
{content}

## Instructions
Review ONLY the changed lines (shown in the diff). For each issue found:
1. Identify the specific line number
2. Describe the issue clearly
3. Suggest a fix
4. Classify severity: "critical" (blocks merge), "major" (should fix), "minor" (optional)

Respond in JSON format:
{{
  "issues": [
    {{
      "line": <line_number>,
      "severity": "critical|major|minor",
      "category": "grammar|spelling|style|syntax|frontmatter|code_blocks|links|images",
      "issue": "Description of the issue",
      "suggestion": "Suggested fix or correction"
    }}
  ],
  "summary": "Brief summary of the review"
}}

If there are no issues, return: {{"issues": [], "summary": "No issues found. Changes look good!"}}
"""

    def _get_file_diff(self, filepath: str) -> str | None:
        """Get the diff for a specific file."""
        comparison = self.repo.compare(self.base_sha, self.head_sha)
        for file in comparison.files:
            if file.filename == filepath:
                return file.patch
        return None

    def _get_file_content(self, filepath: str) -> str | None:
        """Get the current content of a file from the PR head."""
        try:
            content = self.repo.get_contents(filepath, ref=self.head_sha)
            if isinstance(content, list):
                return None
            return content.decoded_content.decode("utf-8")
        except Exception:
            return None

    def _review_file_with_claude(
        self, filepath: str, content: str, diff: str
    ) -> dict[str, Any]:
        """Send file to Claude for review."""
        prompt = self._get_review_prompt(filepath, content, diff)

        try:
            message = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text

            # Parse JSON response
            # Claude might wrap JSON in markdown code blocks
            if "```json" in response_text:
                json_match = re.search(
                    r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL
                )
                if json_match:
                    response_text = json_match.group(1)
            elif "```" in response_text:
                json_match = re.search(r"```\s*(\{.*?\})\s*```", response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)

            return json.loads(response_text)
        except Exception as e:
            print(f"Error reviewing {filepath}: {e!s}")
            return {"issues": [], "summary": f"Error during review: {e!s}"}

    def _post_review_comments(
        self, filepath: str, review_result: dict[str, Any]
    ) -> None:
        """Post review comments to the PR."""
        issues = review_result.get("issues", [])

        if not issues:
            print(f"✓ {filepath}: No issues found")
            return

        print(f"⚠ {filepath}: Found {len(issues)} issue(s)")

        commit = self.repo.get_commit(self.head_sha)

        for issue in issues[: self.config["max_issues_per_file"]]:
            line = issue.get("line")
            severity = issue.get("severity", "minor")
            category = issue.get("category", "general")
            issue_text = issue.get("issue", "")
            suggestion = issue.get("suggestion", "")

            # Format comment
            severity_emoji = {
                "critical": "🚨",
                "major": "⚠️",
                "minor": "ℹ️",
            }
            emoji = severity_emoji.get(severity, "ℹ️")

            comment_body = f"""{emoji} **{severity.upper()}** - {category}

{issue_text}

**Suggestion:**
{suggestion}

---
*AI Documentation Review* | [Severity: {severity}]"""

            try:
                # Post review comment on specific line
                commit.create_comment(
                    body=comment_body,
                    path=filepath,
                    line=line,
                )
            except Exception as e:
                print(f"  Failed to post comment on line {line}: {e!s}")

    def _post_summary_comment(self, review_results: dict[str, dict[str, Any]]) -> None:
        """Post a summary comment to the PR."""
        total_issues = sum(len(r.get("issues", [])) for r in review_results.values())

        if total_issues == 0:
            summary = """## ✅ AI Documentation Review Complete

All changed documentation files look good! No issues found.

The review checked for:
- Grammar and spelling (American English)
- Google Developer Documentation Style Guide adherence
- MDX/Mintlify syntax
- Frontmatter completeness
- Code block formatting and language tags
- Internal link formats
- Image alt text
"""
        else:
            files_with_issues = [
                f
                for f, r in review_results.items()
                if r.get("issues")
            ]

            summary = f"""## 📝 AI Documentation Review Complete

Found **{total_issues} issue(s)** across **{len(files_with_issues)} file(s)**.

### Files Reviewed
"""
            for filepath, result in review_results.items():
                issues = result.get("issues", [])
                if issues:
                    critical = sum(1 for i in issues if i.get("severity") == "critical")
                    major = sum(1 for i in issues if i.get("severity") == "major")
                    minor = sum(1 for i in issues if i.get("severity") == "minor")
                    summary += f"\n- `{filepath}`: {critical} critical, {major} major, {minor} minor"
                else:
                    summary += f"\n- `{filepath}`: ✓ No issues"

            summary += """

### Review Coverage
The review checked for:
- Grammar and spelling (American English)
- Google Developer Documentation Style Guide adherence
- MDX/Mintlify syntax
- Frontmatter completeness
- Code block formatting and language tags
- Internal link formats
- Image alt text

---
*This review only covers changed lines, not pre-existing content.*
"""

        try:
            self.pr.create_issue_comment(summary)
        except Exception as e:
            print(f"Failed to post summary comment: {e!s}")

    def _learn_from_feedback(self) -> None:
        """Analyze PR to learn from accepted/ignored suggestions."""
        # Get all review comments on this PR
        try:
            comments = self.pr.get_review_comments()

            for comment in comments:
                # Check if this is our AI review comment
                if "AI Documentation Review" not in comment.body:
                    continue

                # Check if the comment thread has been resolved or has replies
                # If resolved or has accepting replies, consider it accepted
                # If dismissed/deleted, consider it ignored

                # This is a simplified learning mechanism
                # In a real implementation, you'd track more sophisticated patterns

        except Exception as e:
            print(f"Error learning from feedback: {e!s}")

    def run(self) -> None:
        """Run the PR review process."""
        print(f"Starting AI documentation review for PR #{self.pr_number}")
        print(f"Repository: {self.repo.full_name}")
        print(f"Base: {self.base_sha[:7]}, Head: {self.head_sha[:7]}")

        # Get changed files
        comparison = self.repo.compare(self.base_sha, self.head_sha)
        files_to_review = [
            f.filename for f in comparison.files if self._should_review_file(f.filename)
        ]

        if not files_to_review:
            print("No documentation files to review.")
            sys.exit(0)

        print(f"Found {len(files_to_review)} file(s) to review:")
        for f in files_to_review:
            print(f"  - {f}")

        # Review each file
        review_results: dict[str, dict[str, Any]] = {}

        for filepath in files_to_review:
            print(f"\nReviewing {filepath}...")

            content = self._get_file_content(filepath)
            diff = self._get_file_diff(filepath)

            if not content or not diff:
                print(f"  Skipping {filepath}: Could not fetch content or diff")
                continue

            # Review with Claude
            review_result = self._review_file_with_claude(filepath, content, diff)
            review_results[filepath] = review_result

            # Post comments
            self._post_review_comments(filepath, review_result)

        # Post summary
        self._post_summary_comment(review_results)

        # Learn from feedback (for future runs)
        self._learn_from_feedback()

        # Update feedback data
        self.feedback_data["total_reviews"] += 1
        self._save_feedback_data()

        print("\n✓ Review complete!")


def main() -> None:
    """Main entry point."""
    agent = PRReviewAgent()
    agent.run()


if __name__ == "__main__":
    main()
