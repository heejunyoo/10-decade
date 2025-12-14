#!/bin/bash
# 3-2-1 Backup Strategy Implementation
# Usage: ./scripts/backup.sh

BACKUP_ROOT="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DEST_DIR="$BACKUP_ROOT/$TIMESTAMP"
DB_FILE="decade.db"
UPLOAD_DIR="static/uploads"
LANCE_DB="lancedb_data"

echo "🛡️ Starting Backup Strategy..."
echo "📂 Destination: $DEST_DIR"

# 1. Create Directory
mkdir -p "$DEST_DIR"

# 2. Backup SQLite Database (Use sqlite3 .backup command for safety if possible, or cp if simple)
if [ -f "$DB_FILE" ]; then
    echo "📦 Backing up Database..."
    sqlite3 "$DB_FILE" ".backup '$DEST_DIR/$DB_FILE'"
else
    echo "⚠️ Database file not found!"
fi

# 3. Backup Vector DB (LanceDB)
if [ -d "$LANCE_DB" ]; then
    echo "🧠 Backing up Vector Index..."
    cp -r "$LANCE_DB" "$DEST_DIR/"
fi

# 4. Backup Uploads (Incremental Sync using Rsync locally first)
# We zip them for the archive
echo "📸 Archiving Uploads (This may take time)..."
tar -czf "$DEST_DIR/uploads.tar.gz" "$UPLOAD_DIR"

# 5. Rclone Sync (Cloud Backup)
# Checks if 'gdrive' remote is configured
if rclone listremotes | grep -q "gdrive:"; then
    echo "☁️ Syncing to Google Drive..."
    rclone copy "$DEST_DIR" gdrive:decade_backups/"$TIMESTAMP"
    echo "✅ Cloud Backup Complete."
else
    echo "ℹ️ Rclone 'gdrive' remote not configured. Skipping cloud upload."
    echo "   To configure: rclone config"
fi

# 6. Cleanup (Keep last 7 days locally)
# find "$BACKUP_ROOT" -type d -mtime +7 -exec rm -rf {} \;

echo "✅ Backup Completed Successfully!"
echo "   Location: $DEST_DIR"
