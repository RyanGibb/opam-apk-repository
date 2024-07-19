#!/usr/bin/env bash

script_dir="$(dirname "$0")"
base_url="https://dl-cdn.alpinelinux.org/alpine/"
dir="${script_dir}/../cached"
versions_file="$dir/versions.txt"

curl -o "${dir}/index.html" "${base_url}"

grep -oP '(?<=href=")[^"]*(?=/")' "${dir}/index.html" | grep -E '^v[0-9]+\.[0-9]' | sort -V | awk -F'[v.]' '{ if ($2 > 3 || ($2 == 3 && $3 > 11)) print "v"$2"."$3 }' > "${versions_file}"

rm "${dir}/index.html"

while read -r version; do
    version_dir=""
    apkindex_url="${base_url}${version}/main/x86_64/APKINDEX.tar.gz"
    curl -o "${dir}/${version}-APKINDEX.tar.gz" "${apkindex_url}"
done < "${versions_file}"
