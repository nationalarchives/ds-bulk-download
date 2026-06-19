#!/bin/bash
set -e

until mc alias set local http://minio:9000 "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" >/dev/null 2>&1; do
	sleep 1
done
echo "Minio alias set."

# set a list of buckets to create
buckets=("export" "merlin")

for bucket in "${buckets[@]}"; do
	if mc ls local/"$bucket" >/dev/null 2>&1; then
		echo "Bucket '$bucket' already exists — skipping init."
		continue
	fi
	mc mb local/"$bucket"
	echo "Created bucket '$bucket'."

	cat >/tmp/a-rw.json <<'EOF'
{
"Version": "2012-10-17",
"Statement": [
    { "Effect": "Allow",
    "Action": ["s3:GetBucketLocation","s3:ListBucket"],
    "Resource": ["arn:aws:s3:::${bucket}"]
    },
    { "Effect": "Allow",
    "Action": ["s3:GetObject","s3:PutObject","s3:DeleteObject"],
    "Resource": ["arn:aws:s3:::${bucket}/*"]
    }
]
}
EOF

	mc admin policy create local "${bucket}-rw" /tmp/"${bucket}-rw.json"
	echo "Policy created."

	mc admin accesskey create local --access-key "$ACCESS_KEY" --secret-key "$SECRET_KEY"
	echo "Access key '$ACCESS_KEY' created."

	mc admin policy attach local --user "${ACCESS_KEY}" "${bucket}-rw"
	echo "Policy attached."
done

echo "Init complete."
