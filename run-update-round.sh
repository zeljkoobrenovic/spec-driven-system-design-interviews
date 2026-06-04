codex exec "Review $1 using the review-system-design-interview skill. Commit changes."
claude -p "Improve $1 based on REVIEW.md" --allowedTools "Read,Edit,Bash. Commit changes."
codex exec "Update review of $1 based on recent changes using the review-system-design-interview skill. Commit changes."
claude -p "Improve $1 based on the updated REVIEW.md"
claude -p "Make one more pass in $1 of lightweight edits and polishing to improve understandability, readability, flows, and overall quality. Commit changes."
codex exec "Add external links to $1. Commit changes."

bash generate_images.sh $1
