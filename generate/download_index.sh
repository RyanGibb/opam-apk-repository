#!/usr/bin/env bash

script_dir="$(dirname "$0")"
repo_url="https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64/"
apkindex_url="${repo_url}APKINDEX.tar.gz"
apkindex_local_path="${script_dir}/APKINDEX.tar.gz"
index_html_local_path="${script_dir}/index.html"

curl -o "${apkindex_local_path}" "${apkindex_url}"
curl -o "${index_html_local_path}" "${repo_url}"
