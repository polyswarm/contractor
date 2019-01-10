{
    "ipfs_uri": $ipfs_uri,
    "artifact_limit": $artifact_limit,
    "profiler_enabled": $profiler_enabled,
    "auth_uri": $auth_uri,
}
| del(.[] | nulls)
