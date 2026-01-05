# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

DEEPSEEK_SYSTEM_PROMPT = (
    "You are a Senior Release Engineer. Analyze the provided git commit log. "
    "Your goal is to consolidate the work into a single 'Conventional Commit' message "
    "and suggest a clean git branch name.\n"
    "Output purely valid JSON with no markdown formatting."
)

JULES_CONTEXT_TEMPLATE = "[CONTEXT: {file_path}]\n{content}\n\n"
JULES_INSTRUCTION_HEADER = "[INSTRUCTION]\n{prompt}"
