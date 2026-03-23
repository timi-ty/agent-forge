#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$SCRIPT_DIR/skills"

usage() {
  cat <<EOF
Usage: ./install.sh <skill-name> [--global|--workspace] [--tool cursor|claude-code]
       ./install.sh --all [--global|--workspace] [--tool cursor|claude-code]

Options:
  --global      Install globally (default)
  --workspace   Install to the current directory
  --tool        Target tool: cursor (default) or claude-code
  --all         Install every skill in the catalog

Paths:
  Cursor:      ~/.cursor/skills/     (global)  .cursor/skills/     (workspace)
  Claude Code: ~/.claude/commands/   (global)  .claude/commands/   (workspace)

Examples:
  ./install.sh code-review --global
  ./install.sh commit-agent-changes --workspace --tool claude-code
  ./install.sh --all --global --tool claude-code
EOF
  exit 1
}

install_skill() {
  local name="$1"
  local dest="$2"

  local src="$SKILLS_DIR/$name"
  if [ ! -d "$src" ]; then
    echo "Error: skill '$name' not found in $SKILLS_DIR" >&2
    exit 1
  fi

  local target="$dest/$name"
  mkdir -p "$dest"
  cp -r "$src" "$target"
  echo "Installed '$name' -> $target"
}

[ $# -eq 0 ] && usage

skill_name=""
scope="global"
tool="cursor"
install_all=false

for arg in "$@"; do
  case "$arg" in
    --global)      scope="global" ;;
    --workspace)   scope="workspace" ;;
    --tool)        : ;;  # handled below
    cursor)        tool="cursor" ;;
    claude-code)   tool="claude-code" ;;
    --all)         install_all=true ;;
    --help|-h)     usage ;;
    -*)            echo "Unknown option: $arg" >&2; usage ;;
    *)             skill_name="$arg" ;;
  esac
done

# Re-parse to handle --tool <value> pairs
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  if [[ "${args[$i]}" == "--tool" ]] && (( i+1 < ${#args[@]} )); then
    tool="${args[$((i+1))]}"
    if [[ "$tool" != "cursor" && "$tool" != "claude-code" ]]; then
      echo "Error: --tool must be 'cursor' or 'claude-code'" >&2
      exit 1
    fi
  fi
done

if [ "$install_all" = false ] && [ -z "$skill_name" ]; then
  echo "Error: provide a skill name or --all" >&2
  usage
fi

# Determine destination based on tool and scope
if [ "$tool" = "claude-code" ]; then
  if [ "$scope" = "global" ]; then
    dest="$HOME/.claude/commands"
  else
    dest="$(pwd)/.claude/commands"
  fi
else
  if [ "$scope" = "global" ]; then
    dest="$HOME/.cursor/skills"
  else
    dest="$(pwd)/.cursor/skills"
  fi
fi

if [ "$install_all" = true ]; then
  for dir in "$SKILLS_DIR"/*/; do
    name="$(basename "$dir")"
    install_skill "$name" "$dest"
  done
  echo "All skills installed to $dest"
else
  install_skill "$skill_name" "$dest"
fi
