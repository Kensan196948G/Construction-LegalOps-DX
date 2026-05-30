#!/usr/bin/env bash
# generate_rsa_keys.sh — Generate RSA-2048 key pair for RS256 JWT signing.
#
# Usage:
#   ./scripts/generate_rsa_keys.sh [output_dir]
#
# Output files:
#   jwt_private.pem  — Private key (keep secret, set as JWT_PRIVATE_KEY)
#   jwt_public.pem   — Public key  (can be shared, set as JWT_PUBLIC_KEY)
#
# Environment variable setup (add to .env or Vault):
#   export JWT_PRIVATE_KEY="$(cat jwt_private.pem)"
#   export JWT_PUBLIC_KEY="$(cat jwt_public.pem)"
#   export JWT_ALGORITHM=RS256

set -euo pipefail

OUTPUT_DIR="${1:-.}"
mkdir -p "$OUTPUT_DIR"

PRIVATE_KEY="$OUTPUT_DIR/jwt_private.pem"
PUBLIC_KEY="$OUTPUT_DIR/jwt_public.pem"

if [ -f "$PRIVATE_KEY" ] || [ -f "$PUBLIC_KEY" ]; then
    echo "⚠️  Key files already exist in $OUTPUT_DIR. Aborting to prevent overwrite."
    echo "   Delete manually and re-run if rotation is intended."
    exit 1
fi

echo "🔑 Generating RSA-2048 private key..."
openssl genrsa -out "$PRIVATE_KEY" 2048

echo "🔑 Extracting public key..."
openssl rsa -in "$PRIVATE_KEY" -pubout -out "$PUBLIC_KEY"

chmod 600 "$PRIVATE_KEY"
chmod 644 "$PUBLIC_KEY"

echo ""
echo "✅ Key pair generated:"
echo "   Private: $PRIVATE_KEY (600)"
echo "   Public:  $PUBLIC_KEY  (644)"
echo ""
echo "📋 Set these environment variables (or store in Vault):"
echo "   JWT_PRIVATE_KEY=\$(cat $PRIVATE_KEY)"
echo "   JWT_PUBLIC_KEY=\$(cat $PUBLIC_KEY)"
echo "   JWT_ALGORITHM=RS256"
echo ""
echo "⚠️  NEVER commit jwt_private.pem to git. Add to .gitignore:"
echo "   echo '*.pem' >> .gitignore"
