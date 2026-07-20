#!/usr/bin/env bash
# Movie Cut AWS版のフルデプロイ
#   1. FFmpeg Layer取得（未取得時のみ）
#   2. 共有コード（compressor/, config.py）をworkerへ同期
#   3. sam build && sam deploy
#   4. フロントをビルドしてUIバケットへsync、CloudFront invalidation
set -euo pipefail
cd "$(dirname "$0")"

PROFILE=denwa-dev
REGION=ap-northeast-1
STACK=movie-cut

echo "==> [1/4] FFmpeg Layer"
./layers/ffmpeg/build.sh

echo "==> [2/4] 共有コード同期"
rsync -a --delete --exclude '__pycache__' ../compressor src/worker/
cp ../config.py src/worker/config.py

echo "==> [3/4] sam build & deploy"
sam build
sam deploy

echo "==> [4/4] フロントエンド"
outputs() {
  aws cloudformation describe-stacks --stack-name "$STACK" \
    --profile "$PROFILE" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
UI_BUCKET="$(outputs UiBucketName)"
DIST_ID="$(outputs DistributionId)"
CF_DOMAIN="$(outputs CloudFrontDomain)"

(cd ../frontend && npm install && npm run build)
aws s3 sync ../frontend/dist "s3://$UI_BUCKET" --delete --profile "$PROFILE"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" \
  --paths '/*' --profile "$PROFILE" --output text > /dev/null

echo ""
echo "デプロイ完了: https://$CF_DOMAIN"
