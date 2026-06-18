echo "CODEX: Starting update round for $1 by reviewing the content and improving it based on the review."
codex exec "Review $1 using the review-system-design-interview skill. Commit changes."

echo "CLAUDE: Review of $1 has been updated. Now improving the content based on the review."
claude -p "Improve $1 based on REVIEW.md. Commit changes." --allowedTools "Read,Edit,Bash"

echo "[1/7] CODEX: Updating review of $1 based on recent changes and improving the content based on the review."
codex exec "Update review of $1 based on recent changes using the review-system-design-interview skill. Commit changes."

echo "[2/7] CLAUDE: Improving $1 based on the updated review."
claude -p "Improve $1 based on the updated REVIEW.md" --allowedTools "Read,Edit,Bash"

echo "[3/7] CLAUDE: Polishing $1 for better understandability, readability, flows, and overall quality."
claude -p "Make one more pass in $1 of lightweight edits and polishing to improve understandability, readability, flows, and overall quality. Commit changes." --allowedTools "Read,Edit,Bash"

echo "[4/7] CODEX: Adding technologies choices and external links to $1, and writing a LinkedIn post for $1."
codex exec "Add technologies choices to $1 using the add-technology-choices skill. Commit changes."
echo "[5/7] CODEX: Adding external links to $1."
codex exec "Add external links to $1 using the research-external-links skill. Commit changes."

echo "[6/7] CODEX: Writing a LinkedIn post for $1 and storing it into LINKEDIN.md in the folder of $1."
codex exec "Write a LinkedIn Post for $1 using the write-linkedin-interview-post skill, and store it into LINKEDIN.md in the folder if $1."

echo "[7/7] NANO BANANA: Generating images."
cd _scripts
bash generate_images.sh ../$1

cd ..
python3 build.py