# Follow container logs: powershell -ExecutionPolicy Bypass -File scripts\docker\logs.ps1 [backend|frontend|db]
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..'))
docker compose --env-file .env -f infra/docker-compose.yml logs -f --tail=200 @args
