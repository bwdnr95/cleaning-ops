# Postgres 백업 / 복구 (R10 선반영)

운영 사고 1건이면 데이터가 영구 소실되는 위험을 줄이기 위해 R10보다 먼저 적용한 최소 안전망. cron 자동화는 운영 owner 책임이다.

## 매일 백업 (수동)

```bash
cd /path/to/design_handoff_cleaning_ops
bash scripts/backup.sh
```

산출물: `backups/cleaning_ops_YYYYMMDD_HHMMSSZ.dump.gz` (gzip 압축된 `pg_dump -Fc`).
7일 이상 된 파일은 자동 삭제.

## cron 자동화 (운영 서버 1회 등록)

```cron
# 매일 02:30 KST 백업 + 별도 로그
30 2 * * *  cd /path/to/design_handoff_cleaning_ops && bash scripts/backup.sh >> logs/backup.log 2>&1
```

`logs/` 폴더는 사전 생성. `.gitignore`에 포함.

## 복구

backend(uvicorn)을 먼저 **종료한 뒤** 실행:

```bash
bash scripts/restore.sh backups/cleaning_ops_20260524_173000Z.dump.gz
```

확인 프롬프트에서 `y` 입력. 끝나면 alembic version이 head인지 확인 후 backend 다시 띄움.

## 원격 보관 (권장)

`backups/` 디렉토리를 별도 위치(NAS, 외장 디스크, 또는 R12에서 활성화될 S3)에 매일 1회 동기화. 동일 호스트에 두면 호스트 장애 시 백업도 같이 사라진다.

## 무결성 검증 (월 1회 권장)

최신 dump를 staging DB에 restore 해보고 핵심 테이블 row count 비교:

```bash
docker exec cleanops_postgres psql -U cleanops -d cleaning_ops -c \
  "SELECT 'orders' AS tbl, COUNT(*) FROM orders UNION ALL SELECT 'order_groups', COUNT(*) FROM order_groups;"
```
