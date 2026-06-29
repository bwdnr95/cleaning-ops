import React from 'react';
import { Avatar, Badge, Icon } from '../../components/common/ui';
import {
  addPartnerJobMemo,
  completePartnerJob,
  getPartnerJob,
  getPartnerJobMessages,
  listPartnerJobs,
  startPartnerJob,
} from '../../api/partner';
import { uploadPartnerJobPhoto } from '../../api/photos';
import { ApiError, toApiAssetUrl } from '../../api/client';
import { useApiResource } from '../../api/useApiResource';
import { formatQuantity } from '../../domain/format';
import { digitsOnly, formatPhone } from '../../domain/phone';
import { parseDateValue } from '../../domain/time';

const PARTNER_MESSAGE_TYPE_LABELS = {
  partner_assignment: '작업 배정 안내',
  partner_customer_info: '고객 정보 안내',
};

const PHOTO_UPLOAD_ERROR_MESSAGES = {
  unsupported_photo_type: 'JPG/PNG/WebP만 업로드 가능합니다.',
  photo_too_large: '파일 용량이 초과되었습니다.',
  order_not_found: '배정된 작업을 찾을 수 없습니다.',
  invalid_status_for_upload: '현재 작업 상태에서는 사진을 업로드할 수 없습니다.',
};

const STARTABLE_JOB_STATUSES = ['일정확정', '전날안내필요', '전날안내완료', '작업예정'];
const COMPLETABLE_JOB_STATUSES = ['작업진행'];
// 사진 업로드 허용 상태(백엔드 PARTNER_PHOTO_UPLOADABLE_STATUSES와 일치).
// 활성 작업 구간(시작 가능 상태 + 작업진행)에서만 업로드 버튼을 활성화한다.
const PHOTO_UPLOADABLE_JOB_STATUSES = [...STARTABLE_JOB_STATUSES, ...COMPLETABLE_JOB_STATUSES];

export function PartnerJobDetail({ onDetailOpenChange = undefined } = {}) {
  const [selectedJobId, setSelectedJobId] = React.useState(null);
  const [uploadError, setUploadError] = React.useState(null);
  const [uploadNotice, setUploadNotice] = React.useState(null);
  const [uploadingPhotoType, setUploadingPhotoType] = React.useState(null);
  const [uploadingCount, setUploadingCount] = React.useState(0);
  const [statusError, setStatusError] = React.useState(null);
  const [isUploading, setIsUploading] = React.useState(false);
  const [isSavingStatus, setIsSavingStatus] = React.useState(false);
  const [memoDraft, setMemoDraft] = React.useState('');
  const [memoError, setMemoError] = React.useState(null);
  const [memoNotice, setMemoNotice] = React.useState(null);
  const [isSavingMemo, setIsSavingMemo] = React.useState(false);
  const beforeInputRef = React.useRef<HTMLInputElement | null>(null);
  const afterInputRef = React.useRef<HTMLInputElement | null>(null);
  const etcInputRef = React.useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    onDetailOpenChange?.(Boolean(selectedJobId));
  }, [selectedJobId, onDetailOpenChange]);

  const jobs = useApiResource(listPartnerJobs);
  const detailLoader = React.useCallback(() => {
    if (!selectedJobId) {
      return Promise.resolve(null);
    }
    return getPartnerJob(selectedJobId);
  }, [selectedJobId]);
  const detail = useApiResource(detailLoader, selectedJobId || 'none');
  const selectedFromList = jobs.data?.find((item) => item.id === selectedJobId);
  const job = detail.data || selectedFromList;
  const photoGroups = React.useMemo(() => groupJobPhotos(job?.photos || []), [job?.photos]);

  React.useEffect(() => {
    setUploadError(null);
    setUploadNotice(null);
    setUploadingPhotoType(null);
    setUploadingCount(0);
    setStatusError(null);
    setMemoDraft('');
    setMemoError(null);
    setMemoNotice(null);
  }, [selectedJobId]);

  const refreshFlow = () => {
    jobs.reload();
    detail.reload();
  };

  const handleMemoSave = async () => {
    if (!job) {
      return;
    }
    const text = memoDraft.trim();
    if (!text) {
      return;
    }

    setMemoError(null);
    setMemoNotice(null);
    setIsSavingMemo(true);
    try {
      await addPartnerJobMemo(job.id, text);
      refreshFlow();
      setMemoDraft('');
      setMemoNotice('메모가 저장되었습니다.');
    } catch {
      setMemoError('메모를 저장하지 못했습니다.');
    } finally {
      setIsSavingMemo(false);
    }
  };

  const handlePhotoSelected = async (photoType, event) => {
    const files = [];
    const fileList = event.target.files;
    for (let index = 0; index < (fileList?.length || 0); index += 1) {
      const file = fileList.item(index);
      if (file) {
        files.push(file);
      }
    }
    event.target.value = '';
    if (files.length === 0 || !job) {
      return;
    }

    setUploadError(null);
    setUploadNotice(null);
    setUploadingPhotoType(photoType);
    setUploadingCount(files.length);
    setIsUploading(true);
    let uploadedCount = 0;
    const failedUploads = [];
    for (const file of files) {
      try {
        await uploadPartnerJobPhoto(job.id, { photoType, file });
        uploadedCount += 1;
      } catch (requestError) {
        failedUploads.push({
          fileName: file.name || '이름 없는 파일',
          message: toPhotoUploadErrorMessage(requestError),
        });
      }
    }

    try {
      refreshFlow();
      if (uploadedCount > 0) {
        setUploadNotice(`${photoTypeLabel(photoType)} 사진 ${uploadedCount}장이 업로드되었습니다.`);
      }
      if (failedUploads.length > 0) {
        const failedNames = failedUploads.map((item) => item.fileName).slice(0, 3).join(', ');
        const moreCount = failedUploads.length > 3 ? ` 외 ${failedUploads.length - 3}개` : '';
        const firstReason = failedUploads[0].message;
        setUploadError(`${failedUploads.length}장 업로드 실패: ${failedNames}${moreCount}. ${firstReason}`);
      }
      if (uploadedCount === 0 && failedUploads.length === 0) {
        setUploadError('사진 업로드를 처리하지 못했습니다.');
      }
    } finally {
      setIsUploading(false);
      setUploadingPhotoType(null);
      setUploadingCount(0);
    }
  };

  const handleStatusAction = async (action) => {
    if (!job) {
      return;
    }

    setStatusError(null);
    setIsSavingStatus(true);
    try {
      if (action === 'start') {
        await startPartnerJob(job.id);
      } else {
        await completePartnerJob(job.id);
      }
      refreshFlow();
    } catch (requestError) {
      if (
        requestError instanceof ApiError
        && requestError.detail === 'photo_required_for_completion'
      ) {
        setStatusError('사진을 1장 이상 업로드한 뒤 완료 처리해주세요.');
      } else {
        setStatusError('작업 상태를 변경하지 못했습니다.');
      }
    } finally {
      setIsSavingStatus(false);
    }
  };

  if (jobs.isLoading) {
    return <PartnerState text="작업을 불러오는 중입니다." />;
  }

  if (jobs.error) {
    return <PartnerState text="작업 목록을 불러오지 못했습니다." tone="danger" />;
  }

  if (!selectedJobId) {
    return <PartnerJobList jobs={jobs.data || []} onSelect={setSelectedJobId} onReload={() => jobs.reload()} />;
  }

  if (detail.isLoading && !selectedFromList) {
    return <PartnerState text="작업 상세를 불러오는 중입니다." />;
  }

  if (detail.error || !job) {
    // 현장(지하·약전계)에서 상세 로드가 실패해도 협력사가 갇히지 않도록
    // 다시 시도 + 목록으로 탈출 경로를 항상 제공한다. (상세가 열려 있으면 하단 네비는 숨겨짐)
    return (
      <PartnerState
        text="작업 상세를 불러오지 못했습니다."
        tone="danger"
        actions={(
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" data-testid="partner-detail-retry" onClick={() => detail.reload()} style={partnerStateButtonStyle('brand')}>
              다시 시도
            </button>
            <button type="button" data-testid="partner-detail-back" onClick={() => setSelectedJobId(null)} style={partnerStateButtonStyle('neutral')}>
              목록으로
            </button>
          </div>
        )}
      />
    );
  }

  const canStart = STARTABLE_JOB_STATUSES.includes(job.status);
  const canComplete = COMPLETABLE_JOB_STATUSES.includes(job.status);
  const canUploadPhotos = PHOTO_UPLOADABLE_JOB_STATUSES.includes(job.status);
  const photoUploadDisabled = isUploading || !canUploadPhotos;
  const statusLock = getPartnerStatusLock(job.status);
  const jobAddress = formatJobAddress(job);

  return (
    <div data-testid="partner-job-detail-page" style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#f4f6f8', overflow: 'hidden' }}>
      <div style={{ padding: '12px 16px 10px', background: '#fff', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <button onClick={() => setSelectedJobId(null)} style={{ padding: 0, border: 'none', background: 'transparent', cursor: 'pointer' }}>
            <Icon name="chevronLeft" size={20}/>
          </button>
          <PartnerStatusBadge status={job.status}/>
          {job.is_recurring && <span data-testid="partner-recurring-badge"><Badge tone="brand">정기</Badge></span>}
        </div>
        <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>{job.service_name}</h2>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>{formatQuantity(job.size_or_quantity) || job.service_detail || '상세 수량 미입력'}</div>
      </div>

      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: 12 }}>
        <Panel>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, paddingBottom: 10, borderBottom: '1px solid var(--divider)' }}>
            <span style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--info-bg)', color: 'var(--info-fg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="calendar" size={16}/>
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700 }}>{formatKoreanDate(job.scheduled_date)}</div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{job.requested_time || '시간 협의'}</div>
            </div>
          </div>

          <InfoRow icon="mapPin">
            {jobAddress}<br/>
            <span className="multiline-text" style={{ color: 'var(--text-tertiary)' }}>{job.service_detail || '현장 상세 정보 없음'}</span>
          </InfoRow>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            <ActionButton icon="mapPin" label="지도 열기" href={jobAddress ? `https://map.naver.com/p/search/${encodeURIComponent(jobAddress)}` : undefined} />
            <ActionButton icon="phone" label="고객 전화" href={job.customer_phone ? `tel:${digitsOnly(job.customer_phone)}` : undefined} />
          </div>
        </Panel>

        <Panel>
          <SectionLabel>고객</SectionLabel>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Avatar name={job.customer_name} size={28} tone="brand"/>
            <div>
              <div style={{ fontSize: 13.5, fontWeight: 600 }}>{job.customer_name} 님</div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>{formatPhone(job.customer_phone)}</div>
            </div>
          </div>
          <SectionLabel>특별 요청</SectionLabel>
          <div className="multiline-text" style={{ padding: 10, background: 'var(--warn-bg)', border: '1px solid var(--warn-border)', borderRadius: 8, fontSize: 12.5, lineHeight: 1.5, color: '#78350f' }}>
            {job.special_request || '별도 요청 사항이 없습니다.'}
          </div>
        </Panel>

        <Panel>
          <SectionLabel>작업 메모</SectionLabel>
          <div style={{ display: 'grid', gap: 6, marginBottom: 10 }}>
            {(job.memos || []).length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>작성된 메모가 없습니다.</div>
            ) : (
              (job.memos || []).map((memo, index) => (
                <div key={memo.id || index} data-testid="partner-memo-item" style={{ padding: 10, background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 8 }}>
                  <div className="multiline-text" style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--text)' }}>{memo.text}</div>
                  <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', marginTop: 6 }}>{formatKoreanDateTime(memo.created_at)}</div>
                </div>
              ))
            )}
          </div>
          <textarea
            className="input"
            data-testid="partner-memo-input"
            rows={3}
            maxLength={1000}
            placeholder="현장 메모를 남겨주세요."
            value={memoDraft}
            disabled={isSavingMemo}
            onChange={(event) => setMemoDraft(event.target.value)}
            style={{ width: '100%', height: 'auto', padding: 10, lineHeight: 1.5, resize: 'vertical', fontFamily: 'inherit' }}
          />
          {memoError && <div style={{ fontSize: 11.5, color: 'var(--danger-fg)', marginTop: 6 }}>{memoError}</div>}
          {memoNotice && <div style={{ fontSize: 11.5, color: 'var(--success-fg)', fontWeight: 700, marginTop: 6 }}>{memoNotice}</div>}
          <button
            type="button"
            data-testid="partner-memo-save"
            disabled={isSavingMemo || !memoDraft.trim()}
            onClick={() => void handleMemoSave()}
            style={memoSaveButtonStyle(isSavingMemo || !memoDraft.trim())}
          >
            {isSavingMemo ? '저장 중' : '메모 저장'}
          </button>
        </Panel>

        <PartnerMessagesPanel jobId={job.id} />

        {!canUploadPhotos && (
          <div data-testid="partner-photo-upload-locked" style={{ margin: '0 2px 10px', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg-subtle)', color: 'var(--text-secondary)', fontSize: 11.5, lineHeight: 1.45 }}>
            {photoUploadLockMessage(job.status)}
          </div>
        )}

        <PhotoPanel
          title="비포 사진"
          tone="neutral"
          photos={photoGroups.before}
          onAdd={() => beforeInputRef.current?.click()}
          disabled={photoUploadDisabled}
        />
        <input ref={beforeInputRef} data-testid="partner-before-photo-input" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple style={{ display: 'none' }} onChange={(event) => void handlePhotoSelected('before', event)} />

        <PhotoPanel
          title="애프터 사진"
          tone="success"
          photos={photoGroups.after}
          onAdd={() => afterInputRef.current?.click()}
          disabled={photoUploadDisabled}
        />
        <input ref={afterInputRef} data-testid="partner-after-photo-input" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple style={{ display: 'none' }} onChange={(event) => void handlePhotoSelected('after', event)} />
        <PhotoPanel
          title="기타 사진"
          tone="brand"
          photos={photoGroups.etc}
          onAdd={() => etcInputRef.current?.click()}
          disabled={photoUploadDisabled}
        />
        <input ref={etcInputRef} data-testid="partner-etc-photo-input" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple style={{ display: 'none' }} onChange={(event) => void handlePhotoSelected('etc', event)} />
        {isUploading && (
          <div data-testid="partner-photo-upload-status" style={{ margin: '-2px 2px 10px', color: 'var(--brand)', fontSize: 11.5, fontWeight: 700 }}>
            {photoTypeLabel(uploadingPhotoType)} 사진 {uploadingCount}장 업로드 중입니다.
          </div>
        )}
        {!isUploading && uploadNotice && (
          <div data-testid="partner-photo-upload-status" style={{ margin: '-2px 2px 10px', color: 'var(--success-fg)', fontSize: 11.5, fontWeight: 700 }}>
            {uploadNotice}
          </div>
        )}
        {uploadError && <div style={{ margin: '-2px 2px 10px', color: 'var(--danger-fg)', fontSize: 11.5 }}>{uploadError}</div>}
      </div>

      <div style={{ padding: '10px 14px 12px', background: '#fff', borderTop: '1px solid var(--border)', boxShadow: '0 -4px 12px rgba(15,23,42,0.04)' }}>
        {canStart || canComplete ? (
          <div style={{ display: 'grid', gridTemplateColumns: canStart && canComplete ? '1fr 1fr' : '1fr', gap: 8 }}>
            {canStart && (
              <button data-testid="partner-start-job" disabled={isSavingStatus} onClick={() => void handleStatusAction('start')} style={secondaryCtaStyle(isSavingStatus)}>
                <Icon name="clock" size={16}/> 작업 시작
              </button>
            )}
            {canComplete && (
              <button data-testid="partner-complete-job" disabled={isSavingStatus} onClick={() => void handleStatusAction('complete')} style={primaryCtaStyle(isSavingStatus)}>
                <Icon name="check" size={16}/> 작업 완료
              </button>
            )}
          </div>
        ) : (
          <div data-testid="partner-status-locked" style={{ minHeight: 48, border: '1px solid var(--border)', borderRadius: 10, background: statusLock.tone === 'danger' ? 'var(--danger-bg)' : 'var(--bg-subtle)', color: statusLock.tone === 'danger' ? 'var(--danger-fg)' : 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px' }}>
            <span style={{ width: 30, height: 30, borderRadius: 8, background: statusLock.tone === 'success' ? 'var(--success-bg)' : statusLock.tone === 'danger' ? 'var(--danger-bg)' : 'var(--warn-bg)', color: statusLock.tone === 'success' ? 'var(--success-fg)' : statusLock.tone === 'danger' ? 'var(--danger-fg)' : 'var(--warn-fg)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <Icon name={statusLock.icon} size={15}/>
            </span>
            <span style={{ minWidth: 0 }}>
              <span style={{ display: 'block', fontSize: 12.5, fontWeight: 800, color: 'var(--text)' }}>{statusLock.title}</span>
              <span style={{ display: 'block', fontSize: 11, color: 'var(--text-tertiary)', marginTop: 1 }}>{statusLock.description}</span>
            </span>
          </div>
        )}
        {statusError && <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--danger-fg)', marginTop: 6 }}>{statusError}</div>}
        <div style={{ textAlign: 'center', fontSize: 10.5, color: 'var(--text-tertiary)', marginTop: 6 }}>
          사진은 업로드 즉시 고객에게 공개됩니다. 잘못 올렸다면 운영팀에 비공개 처리를 요청해주세요.
        </div>
      </div>
    </div>
  );
}

function formatJobAddress(job) {
  return [job.customer_address, job.customer_address_detail].filter(Boolean).join(' ');
}

function PartnerJobList({ jobs, onSelect, onReload = undefined }) {
  return (
    <div data-testid="partner-jobs-page" style={{ height: '100%', background: '#f4f6f8', overflow: 'auto', padding: 14 }}>
      <PartnerHomeHero jobs={jobs} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <h2 style={{ margin: 0, fontSize: 16.5, fontWeight: 800 }}>
          내 작업
          {jobs.length > 0 && (
            <span style={{ marginLeft: 6, fontSize: 13, fontWeight: 600, color: 'var(--text-tertiary)' }}>{jobs.length}건</span>
          )}
        </h2>
        <div style={{ flex: 1 }} />
        {onReload && (
          <button
            type="button"
            data-testid="partner-jobs-refresh"
            onClick={onReload}
            aria-label="새로고침"
            style={{ width: 34, height: 34, flexShrink: 0, borderRadius: 9, border: '1px solid var(--border)', background: '#fff', color: 'var(--text-secondary)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
          >
            <Icon name="refresh" size={15} />
          </button>
        )}
      </div>

      {jobs.length === 0 ? (
        <div data-testid="partner-jobs-empty" style={{ marginTop: 8, background: '#fff', border: '1px solid var(--border)', borderRadius: 12, padding: '34px 20px', textAlign: 'center' }}>
          <div style={{ width: 54, height: 54, margin: '0 auto 14px', borderRadius: 15, background: 'var(--brand-bg)', color: 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="inbox" size={26} />
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 6 }}>배정된 작업이 없습니다</div>
          <div style={{ fontSize: 12.5, color: 'var(--text-tertiary)', lineHeight: 1.55 }}>
            운영팀이 작업을 배정하면<br />이곳에 자동으로 표시됩니다.
          </div>
          {onReload && (
            <button
              type="button"
              onClick={onReload}
              style={{ marginTop: 18, height: 40, padding: '0 18px', borderRadius: 10, border: '1px solid var(--brand)', background: '#fff', color: 'var(--brand)', fontSize: 13, fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}
            >
              <Icon name="refresh" size={14} /> 새로고침
            </button>
          )}
        </div>
      ) : (
      <div style={{ display: 'grid', gap: 10 }}>
        {jobs.map((job) => (
          <button key={job.id} data-testid={`partner-job-row-${job.id}`} onClick={() => onSelect(job.id)} style={{ textAlign: 'left', background: '#fff', border: '1px solid var(--border)', borderRadius: 10, padding: 14, cursor: 'pointer' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <PartnerStatusBadge status={job.status}/>
              {job.is_recurring && <span data-testid="partner-recurring-badge"><Badge tone="brand">정기</Badge></span>}
              <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-tertiary)' }}>{formatKoreanDate(job.scheduled_date)}</span>
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>{job.service_name}</div>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.45 }}>{formatJobAddress(job)}</div>
            <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--brand)', fontSize: 12.5, fontWeight: 700 }}>
              상세 보기 <Icon name="chevronRight" size={14}/>
            </div>
          </button>
        ))}
      </div>
      )}
    </div>
  );
}

function PartnerHomeHero({ jobs }) {
  const summary = summarizeJobs(jobs);
  return (
    <div data-testid="partner-home-hero" style={{ background: 'var(--brand)', borderRadius: 14, padding: '15px 16px 14px', marginBottom: 14, color: '#fff', boxShadow: '0 6px 16px rgba(15,23,42,0.12)' }}>
      <div style={{ fontSize: 12, opacity: 0.85, display: 'flex', alignItems: 'center', gap: 5 }}>
        <Icon name="calendar" size={13} color="#fff" /> {todayLabel()}
      </div>
      <div style={{ fontSize: 17, fontWeight: 800, marginTop: 4, letterSpacing: '-0.01em' }}>
        {jobs.length > 0 ? `오늘 처리할 작업 ${jobs.length}건` : '오늘은 배정된 작업이 없어요'}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 13 }}>
        <HeroStat label="예정" value={summary.upcoming} />
        <HeroStat label="진행" value={summary.inProgress} />
        <HeroStat label="완료" value={summary.done} />
      </div>
    </div>
  );
}

function HeroStat({ label, value }) {
  return (
    <div style={{ flex: 1, background: 'rgba(255,255,255,0.16)', borderRadius: 10, padding: '9px 6px', textAlign: 'center' }}>
      <div style={{ fontSize: 19, fontWeight: 800, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 11, opacity: 0.92, marginTop: 4 }}>{label}</div>
    </div>
  );
}

function summarizeJobs(jobs) {
  const doneStatuses = ['사진검수대기', '고객전달필요', '고객전달완료', '고객확인필요', '서비스완료'];
  let upcoming = 0;
  let inProgress = 0;
  let done = 0;
  for (const job of jobs) {
    if (job.status === '작업진행') {
      inProgress += 1;
    } else if (doneStatuses.includes(job.status)) {
      done += 1;
    } else {
      upcoming += 1;
    }
  }
  return { upcoming, inProgress, done };
}

function todayLabel() {
  const now = new Date();
  const weekday = ['일', '월', '화', '수', '목', '금', '토'][now.getDay()];
  return `${now.getMonth() + 1}월 ${now.getDate()}일 ${weekday}요일`;
}

function PhotoPanel({ title, tone, photos, onAdd, disabled }) {
  return (
    <Panel>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{title}</span>
        <Badge tone={tone}>{photos.length}장</Badge>
        <div style={{ flex: 1 }}/>
        <button onClick={onAdd} disabled={disabled} style={{ height: 26, padding: '0 10px', border: 'none', borderRadius: 6, background: tone === 'success' ? 'var(--success-bg)' : 'var(--brand-bg)', color: tone === 'success' ? 'var(--success-fg)' : 'var(--brand)', fontSize: 12, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 4, cursor: disabled ? 'default' : 'pointer' }}>
          <Icon name="plus" size={12}/> 추가
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
        {photos.map((photo, index) => (
          <figure key={photo.id || index} data-testid={`partner-photo-thumb-${photo.id}`} style={{ margin: 0, position: 'relative', aspectRatio: '1', overflow: 'hidden', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-muted)' }}>
            <img
              src={toApiAssetUrl(photo.file_url)}
              alt={photo.file_name || `${title} ${index + 1}`}
              loading="lazy"
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
            />
            <span style={{ position: 'absolute', left: 4, bottom: 4, maxWidth: 'calc(100% - 8px)', height: 16, padding: '0 4px', borderRadius: 4, background: 'rgba(15,23,42,0.78)', color: '#fff', fontSize: 9, fontWeight: 700, display: 'inline-flex', alignItems: 'center' }}>
              {index + 1}
            </span>
          </figure>
        ))}
        <button onClick={onAdd} disabled={disabled} style={{ aspectRatio: '1', border: '1.5px dashed var(--border-strong)', borderRadius: 6, background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: disabled ? 'default' : 'pointer', flexDirection: 'column', gap: 2, color: 'var(--text-tertiary)' }}>
          <Icon name="camera" size={16}/>
          <span style={{ fontSize: 9.5 }}>{disabled ? '업로드 중' : '촬영'}</span>
        </button>
      </div>
    </Panel>
  );
}

function PartnerMessagesPanel({ jobId }) {
  const loader = React.useCallback(() => {
    if (!jobId) {
      return Promise.resolve([]);
    }
    return getPartnerJobMessages(jobId);
  }, [jobId]);
  const messages = useApiResource(loader, jobId || 'none');
  const items = messages.data || [];

  let body;
  if (messages.isLoading) {
    body = <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>불러오는 중</div>;
  } else if (messages.error) {
    body = <div style={{ fontSize: 12, color: 'var(--danger-fg)' }}>안내 내역을 불러오지 못했습니다.</div>;
  } else if (items.length === 0) {
    body = <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>받은 안내가 없습니다.</div>;
  } else {
    body = (
      <div style={{ display: 'grid', gap: 8 }}>
        {items.map((message, index) => (
          <div key={message.id || index} style={{ padding: 10, background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 700 }}>{partnerMessageTypeLabel(message.message_type)}</span>
              <span style={{ marginLeft: 'auto' }}><Badge tone={messageStatusTone(message.status)}>{messageStatusLabel(message.status)}</Badge></span>
            </div>
            <div className="multiline-text" style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--text)' }}>{message.content}</div>
            <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', marginTop: 6 }}>{formatKoreanDateTime(message.sent_at || message.created_at)}</div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div data-testid="partner-messages-panel" style={{ background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, border: '1px solid var(--border)' }}>
      <SectionLabel>운영팀 안내</SectionLabel>
      {body}
    </div>
  );
}

function Panel({ children }) {
  return <div style={{ background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, border: '1px solid var(--border)' }}>{children}</div>;
}

function InfoRow({ icon, children }) {
  return (
    <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
      <span style={{ width: 16, marginTop: 2 }}><Icon name={icon} size={14} color="var(--text-tertiary)"/></span>
      <div style={{ flex: 1, fontSize: 13, lineHeight: 1.5 }}>{children}</div>
    </div>
  );
}

function ActionButton({ icon, label, href }) {
  const commonStyle = {
    height: 36,
    border: '1px solid var(--border)',
    borderRadius: 8,
    background: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    fontSize: 12.5,
    fontWeight: 500,
    color: href ? 'var(--text)' : 'var(--text-tertiary)',
    textDecoration: 'none',
    cursor: href ? 'pointer' : 'default',
  };

  if (!href) {
    return (
      <button disabled style={commonStyle}>
        <Icon name={icon} size={14} color="var(--text-tertiary)"/> {label}
      </button>
    );
  }

  return (
    <a href={href} target={href.startsWith('http') ? '_blank' : undefined} rel={href.startsWith('http') ? 'noreferrer' : undefined} style={commonStyle}>
      <Icon name={icon} size={14} color="var(--brand)"/> {label}
    </a>
  );
}

function SectionLabel({ children }) {
  return <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 6 }}>{children}</div>;
}

function PartnerStatusBadge({ status }) {
  const label = partnerStatusLabel(status);
  const tone = partnerStatusTone(status);
  return <Badge tone={tone} dot>{label}</Badge>;
}

function PartnerState({ text, tone = 'muted', actions = null }) {
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, padding: 24, background: '#f4f6f8', color: tone === 'danger' ? 'var(--danger-fg)' : 'var(--text-tertiary)', fontSize: 13, textAlign: 'center' }}>
      <div>{text}</div>
      {actions}
    </div>
  );
}

function partnerStateButtonStyle(variant) {
  const isBrand = variant === 'brand';
  return {
    height: 40,
    padding: '0 16px',
    borderRadius: 10,
    border: isBrand ? 'none' : '1px solid var(--border)',
    background: isBrand ? 'var(--brand)' : '#fff',
    color: isBrand ? '#fff' : 'var(--text)',
    fontSize: 13,
    fontWeight: 700,
    cursor: 'pointer',
  };
}

function groupJobPhotos(photos) {
  const groups = {
    before: [],
    after: [],
    etc: [],
  };

  for (const photo of photos) {
    if (photo.photo_type === 'before') {
      groups.before.push(photo);
    } else if (photo.photo_type === 'after') {
      groups.after.push(photo);
    } else {
      groups.etc.push(photo);
    }
  }

  return groups;
}

function toPhotoUploadErrorMessage(error) {
  if (error instanceof ApiError) {
    const detail = typeof error.detail === 'string' ? error.detail : '';
    if (PHOTO_UPLOAD_ERROR_MESSAGES[detail]) {
      return PHOTO_UPLOAD_ERROR_MESSAGES[detail];
    }
    if (error.status === 413) {
      return PHOTO_UPLOAD_ERROR_MESSAGES.photo_too_large;
    }
    if (error.status === 422) {
      return '사진 유형과 파일을 확인해주세요.';
    }
  }

  return '사진 업로드를 처리하지 못했습니다.';
}

function photoUploadLockMessage(status) {
  if (status === '취소') {
    return '취소된 작업이라 사진을 업로드할 수 없습니다.';
  }
  if (['고객전달완료', '서비스완료'].includes(status)) {
    return '완료된 작업이라 사진 업로드가 잠겼습니다. 추가 사진이 필요하면 운영팀에 요청해주세요.';
  }
  if (['사진검수대기', '고객전달필요'].includes(status)) {
    return '작업 완료 처리되어 사진 업로드가 잠겼습니다. 잘못 올린 사진은 운영팀에 비공개 처리를 요청해주세요.';
  }
  return '일정이 확정되어 작업 구간에 들어서면 사진을 업로드할 수 있습니다.';
}

function photoTypeLabel(type) {
  if (type === 'before') {
    return '비포';
  }
  if (type === 'after') {
    return '애프터';
  }
  return '기타';
}

function formatKoreanDate(value) {
  if (!value) {
    return '일정 미정';
  }

  const date = parseDateValue(value);
  if (!date) {
    return value;
  }
  const weekday = ['일', '월', '화', '수', '목', '금', '토'][date.getDay()];
  return `${date.getMonth() + 1}월 ${date.getDate()}일 ${weekday}요일`;
}

function formatKoreanDateTime(value) {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${date.getMonth() + 1}월 ${date.getDate()}일 ${hours}:${minutes}`;
}

function partnerMessageTypeLabel(type) {
  return PARTNER_MESSAGE_TYPE_LABELS[type] || type || '안내';
}

function messageStatusLabel(status) {
  if (status === 'sent' || status === 'success') {
    return '발송 완료';
  }
  if (status === 'failed' || status === 'error') {
    return '발송 실패';
  }
  if (status === 'pending' || status === 'queued') {
    return '발송 대기';
  }
  return status || '-';
}

function messageStatusTone(status) {
  if (status === 'sent' || status === 'success') {
    return 'success';
  }
  if (status === 'failed' || status === 'error') {
    return 'danger';
  }
  return 'neutral';
}

function memoSaveButtonStyle(disabled) {
  return {
    width: '100%',
    height: 44,
    marginTop: 8,
    background: disabled ? 'var(--bg-subtle)' : 'var(--brand)',
    color: disabled ? 'var(--text-tertiary)' : '#fff',
    border: disabled ? '1px solid var(--border)' : 'none',
    borderRadius: 10,
    fontSize: 14,
    fontWeight: 700,
    cursor: disabled ? 'default' : 'pointer',
  };
}

function partnerStatusLabel(status) {
  if (status === '취소') {
    return '취소';
  }
  if (status === '작업진행') {
    return '작업 중';
  }
  if (['사진검수대기', '고객전달필요'].includes(status)) {
    return '완료 확인 중';
  }
  if (['고객전달완료', '서비스완료'].includes(status)) {
    return '완료';
  }
  if (['신규접수', '상담중', '협력사확인중'].includes(status)) {
    return '확인 중';
  }
  return '작업 예정';
}

function partnerStatusTone(status) {
  if (status === '취소') {
    return 'danger';
  }
  if (['고객전달완료', '서비스완료'].includes(status)) {
    return 'success';
  }
  if (['사진검수대기', '고객전달필요'].includes(status)) {
    return 'warn';
  }
  if (status === '작업진행') {
    return 'info';
  }
  return 'neutral';
}

function getPartnerStatusLock(status) {
  if (status === '취소') {
    return {
      icon: 'x',
      tone: 'danger',
      title: '취소된 작업입니다',
      description: '운영팀에서 취소 처리한 작업이라 현장 액션을 사용할 수 없습니다.',
    };
  }
  if (['고객전달완료', '서비스완료'].includes(status)) {
    return {
      icon: 'check',
      tone: 'success',
      title: '서비스 완료된 작업입니다',
      description: '고객 전달까지 완료되어 추가 작업 상태 변경이 잠겼습니다.',
    };
  }
  if (['사진검수대기', '고객전달필요'].includes(status)) {
    return {
      icon: 'lock',
      tone: 'warn',
      title: '작업 완료 처리됨',
      description: '고객 사진 링크 발송 단계로 넘어간 작업입니다. 잘못 올린 사진은 운영팀에 비공개 처리를 요청해주세요.',
    };
  }
  return {
    icon: 'clock',
    tone: 'neutral',
    title: '운영팀 확인 중입니다',
    description: '일정이 확정되면 작업 시작을 사용할 수 있습니다.',
  };
}

function primaryCtaStyle(disabled) {
  return {
    width: '100%',
    height: 46,
    background: 'var(--brand)',
    color: '#fff',
    border: 'none',
    borderRadius: 10,
    fontSize: 14.5,
    fontWeight: 700,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    cursor: disabled ? 'default' : 'pointer',
  };
}

function secondaryCtaStyle(disabled) {
  return {
    ...primaryCtaStyle(disabled),
    background: '#fff',
    color: 'var(--brand)',
    border: '1px solid var(--brand)',
  };
}
