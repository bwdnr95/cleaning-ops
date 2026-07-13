import React from 'react';
import { PhotoLightbox } from '../../components/common/PhotoLightbox';
import { ProtectedApiImage } from '../../components/common/ProtectedApiImage';
import { Avatar, Badge, Icon } from '../../components/common/ui';
import {
  addPartnerJobMemo,
  completePartnerJob,
  confirmPartnerJob,
  getPartnerJob,
  getPartnerJobMessages,
  listPartnerJobs,
  startPartnerJob,
} from '../../api/partner';
import { PartnerSignaturePad } from './PartnerSignaturePad';
import { deletePartnerJobPhoto, uploadPartnerJobPhoto } from '../../api/photos';
import { ApiError } from '../../api/client';
import { useApiResource } from '../../api/useApiResource';
import { useAuth } from '../../store/authStore';
import { formatQuantity } from '../../domain/format';
import { digitsOnly, formatPhone } from '../../domain/phone';
import { parseDateValue } from '../../domain/time';

const PARTNER_MESSAGE_TYPE_LABELS = {
  partner_assignment: '작업 배정 안내',
  partner_customer_info: '고객 정보 안내',
  partner_as_request: 'AS 요청 안내',
};

const PHOTO_UPLOAD_ERROR_MESSAGES = {
  unsupported_photo_type: 'JPG/PNG/WebP만 업로드 가능합니다.',
  photo_too_large: '파일 용량이 초과되었습니다.',
  order_not_found: '배정된 작업을 찾을 수 없습니다.',
  invalid_status_for_upload: '현재 작업 상태에서는 사진을 업로드할 수 없습니다.',
};

const CONFIRMABLE_JOB_STATUSES = ['협력사확인중'];
const STARTABLE_JOB_STATUSES = ['일정확정', '전날안내필요', '전날안내완료', '작업예정', '고객확인필요'];
const COMPLETABLE_JOB_STATUSES = ['작업진행'];
// 사진 업로드 허용 상태(백엔드 PARTNER_PHOTO_UPLOADABLE_STATUSES와 일치).
// 활성 작업 구간(시작 가능 상태 + 작업진행)에서만 업로드 버튼을 활성화한다.
const PHOTO_UPLOADABLE_JOB_STATUSES = [...STARTABLE_JOB_STATUSES, ...COMPLETABLE_JOB_STATUSES];

export function PartnerJobDetail({ onDetailOpenChange = undefined } = {}) {
  const [selectedJobId, setSelectedJobId] = React.useState(() => readInitialPartnerJobId());
  const [uploadError, setUploadError] = React.useState(null);
  const [uploadNotice, setUploadNotice] = React.useState(null);
  const [uploadingPhotoType, setUploadingPhotoType] = React.useState(null);
  const [uploadingCount, setUploadingCount] = React.useState(0);
  const [deletingPhotoId, setDeletingPhotoId] = React.useState(null);
  const [statusError, setStatusError] = React.useState(null);
  const [isUploading, setIsUploading] = React.useState(false);
  const [isSavingStatus, setIsSavingStatus] = React.useState(false);
  const [memoDraft, setMemoDraft] = React.useState('');
  const [memoError, setMemoError] = React.useState(null);
  const [memoNotice, setMemoNotice] = React.useState(null);
  const [isSavingMemo, setIsSavingMemo] = React.useState(false);
  const [signatureDataUrl, setSignatureDataUrl] = React.useState('');
  const [openPhotoId, setOpenPhotoId] = React.useState<string | null>(null);
  const beforeCameraInputRef = React.useRef<HTMLInputElement | null>(null);
  const beforeAlbumInputRef = React.useRef<HTMLInputElement | null>(null);
  const afterCameraInputRef = React.useRef<HTMLInputElement | null>(null);
  const afterAlbumInputRef = React.useRef<HTMLInputElement | null>(null);
  const etcCameraInputRef = React.useRef<HTMLInputElement | null>(null);
  const etcAlbumInputRef = React.useRef<HTMLInputElement | null>(null);

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
  const currentEvidencePhotoGroups = React.useMemo(
    () => groupJobPhotos(filterCurrentEvidencePhotos(job)),
    [job],
  );
  const lightboxPhotos = React.useMemo(
    () => (job?.photos || []).map((photo) => ({
      id: photo.id,
      src: photo.file_url,
      alt: photo.file_name || photoTypeLabel(photo.photo_type),
      caption: photo.file_name || photoTypeLabel(photo.photo_type),
      isProtected: true,
    })),
    [job?.photos],
  );

  React.useEffect(() => {
    setUploadError(null);
    setUploadNotice(null);
    setUploadingPhotoType(null);
    setUploadingCount(0);
    setDeletingPhotoId(null);
    setStatusError(null);
    setMemoDraft('');
    setMemoError(null);
    setMemoNotice(null);
    setSignatureDataUrl('');
    setOpenPhotoId(null);
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

  const handlePhotoDelete = async (photo) => {
    if (!job || !photo?.id || deletingPhotoId) {
      return;
    }
    if (!window.confirm('이 사진을 삭제할까요?')) {
      return;
    }

    setUploadError(null);
    setUploadNotice(null);
    setDeletingPhotoId(photo.id);
    try {
      await deletePartnerJobPhoto(job.id, photo.id);
      if (openPhotoId === photo.id) {
        setOpenPhotoId(null);
      }
      refreshFlow();
      setUploadNotice(`${photoTypeLabel(photo.photo_type)} 사진을 삭제했습니다.`);
    } catch (requestError) {
      setUploadError(toPhotoDeleteErrorMessage(requestError));
    } finally {
      setDeletingPhotoId(null);
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
      } else if (action === 'confirm') {
        await confirmPartnerJob(job.id);
      } else {
        await completePartnerJob(job.id, signatureDataUrl);
      }
      refreshFlow();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.detail === 'before_photo_required_for_start') {
        setStatusError('비포 사진을 1장 이상 업로드한 뒤 작업을 시작해주세요.');
      } else if (requestError instanceof ApiError && requestError.detail === 'completion_evidence_required') {
        setStatusError('비포/애프터 사진과 고객 서명을 모두 준비한 뒤 완료 처리해주세요.');
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

  const canConfirm = CONFIRMABLE_JOB_STATUSES.includes(job.status);
  const canUseFieldActions = isPartnerFieldActionReady(job);
  const canStart = STARTABLE_JOB_STATUSES.includes(job.status) && canUseFieldActions;
  const canComplete = COMPLETABLE_JOB_STATUSES.includes(job.status);
  const canUploadPhotos = PHOTO_UPLOADABLE_JOB_STATUSES.includes(job.status) && canUseFieldActions;
  const photoUploadDisabled = isUploading || !canUploadPhotos;
  const canDeletePhotos = canUploadPhotos && !isUploading && !deletingPhotoId;
  const statusLock = getPartnerStatusLock(job.status, job.as_requested);
  const jobAddress = formatJobAddress(job);
  const hasBeforePhoto = currentEvidencePhotoGroups.before.length > 0;
  const hasAfterPhoto = currentEvidencePhotoGroups.after.length > 0;
  const hasCurrentSignature = Boolean(signatureDataUrl);
  const hasRecordedSignature = hasCurrentSignature || Boolean(job.has_recorded_customer_signature);
  const hasChecklistSignature = canComplete ? hasCurrentSignature : hasRecordedSignature;
  const canSubmitStart = canStart && hasBeforePhoto;
  const canSubmitComplete = canComplete && hasBeforePhoto && hasAfterPhoto && hasCurrentSignature;
  const footerHelpText = partnerFooterHelpText(job.status, job.as_requested);

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
          {job.as_requested && (
            <div style={{ marginTop: 10 }}>
              <SectionLabel>AS 요청 (재작업)</SectionLabel>
              <div
                className="multiline-text"
                data-testid="partner-as-block"
                style={{ padding: 10, background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: 8, fontSize: 12.5, lineHeight: 1.5, color: 'var(--danger-fg)', fontWeight: 500 }}
              >
                {job.as_memo || 'AS(재작업) 요청이 접수되었습니다. 관리자와 일정을 조율해주세요.'}
              </div>
            </div>
          )}
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
            {photoUploadLockMessage(job.status, job.as_requested)}
          </div>
        )}

        <PhotoPanel
          title="비포 사진"
          tone="neutral"
          photos={photoGroups.before}
          onCapture={() => beforeCameraInputRef.current?.click()}
          onPick={() => beforeAlbumInputRef.current?.click()}
          disabled={photoUploadDisabled}
          isUploading={isUploading}
          onOpenPhoto={setOpenPhotoId}
          canDelete={canDeletePhotos}
          deletingPhotoId={deletingPhotoId}
          onDeletePhoto={handlePhotoDelete}
        />
        <input ref={beforeCameraInputRef} data-testid="partner-before-photo-camera-input" type="file" accept="image/*" capture="environment" style={{ display: 'none' }} onChange={(event) => void handlePhotoSelected('before', event)} />
        <input ref={beforeAlbumInputRef} data-testid="partner-before-photo-album-input" type="file" accept="image/jpeg,image/png,image/webp" multiple style={{ display: 'none' }} onChange={(event) => void handlePhotoSelected('before', event)} />

        <PhotoPanel
          title="애프터 사진"
          tone="success"
          photos={photoGroups.after}
          onCapture={() => afterCameraInputRef.current?.click()}
          onPick={() => afterAlbumInputRef.current?.click()}
          disabled={photoUploadDisabled}
          isUploading={isUploading}
          onOpenPhoto={setOpenPhotoId}
          canDelete={canDeletePhotos}
          deletingPhotoId={deletingPhotoId}
          onDeletePhoto={handlePhotoDelete}
        />
        <input ref={afterCameraInputRef} data-testid="partner-after-photo-camera-input" type="file" accept="image/*" capture="environment" style={{ display: 'none' }} onChange={(event) => void handlePhotoSelected('after', event)} />
        <input ref={afterAlbumInputRef} data-testid="partner-after-photo-album-input" type="file" accept="image/jpeg,image/png,image/webp" multiple style={{ display: 'none' }} onChange={(event) => void handlePhotoSelected('after', event)} />
        <PhotoPanel
          title="기타 사진"
          tone="brand"
          photos={photoGroups.etc}
          onCapture={() => etcCameraInputRef.current?.click()}
          onPick={() => etcAlbumInputRef.current?.click()}
          disabled={photoUploadDisabled}
          isUploading={isUploading}
          onOpenPhoto={setOpenPhotoId}
          canDelete={canDeletePhotos}
          deletingPhotoId={deletingPhotoId}
          onDeletePhoto={handlePhotoDelete}
        />
        <input ref={etcCameraInputRef} data-testid="partner-etc-photo-camera-input" type="file" accept="image/*" capture="environment" style={{ display: 'none' }} onChange={(event) => void handlePhotoSelected('etc', event)} />
        <input ref={etcAlbumInputRef} data-testid="partner-etc-photo-album-input" type="file" accept="image/jpeg,image/png,image/webp" multiple style={{ display: 'none' }} onChange={(event) => void handlePhotoSelected('etc', event)} />
        {photoGroups.customerAs.length > 0 && (
          <PhotoPanel
            title="고객 AS 접수 사진"
            tone="warn"
            photos={photoGroups.customerAs}
            showUpload={false}
            disabled
            onOpenPhoto={setOpenPhotoId}
          />
        )}
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

        {(canStart || canComplete || job.has_recorded_customer_signature) && (
          <EvidenceChecklist
            hasBeforePhoto={hasBeforePhoto}
            hasAfterPhoto={hasAfterPhoto}
            hasSignature={hasChecklistSignature}
            canComplete={canComplete}
            startedAt={job.work_started_at}
            completedAt={job.work_completed_at}
          />
        )}

        {canComplete && (
          <Panel>
            <SectionLabel>고객 서명</SectionLabel>
            {job.has_recorded_customer_signature && !signatureDataUrl && (
              <div style={{ marginBottom: 8, fontSize: 11.5, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
                이전 서명 기록이 있어도 이번 작업 완료에는 고객님의 새 서명이 필요합니다.
              </div>
            )}
            <PartnerSignaturePad
              value={signatureDataUrl}
              onChange={setSignatureDataUrl}
              disabled={isSavingStatus}
            />
          </Panel>
        )}
      </div>

      <div style={{ padding: '10px 14px calc(12px + env(safe-area-inset-bottom))', background: '#fff', borderTop: '1px solid var(--border)', boxShadow: '0 -4px 12px rgba(15,23,42,0.04)' }}>
        {canConfirm || canStart || canComplete ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 8 }}>
            {canConfirm && (
              <button data-testid="partner-confirm-job" disabled={isSavingStatus} onClick={() => void handleStatusAction('confirm')} style={primaryCtaStyle(isSavingStatus)}>
                <Icon name="check" size={16}/> 작업 일정 확인
              </button>
            )}
            {canStart && (
              <button data-testid="partner-start-job" disabled={isSavingStatus || !canSubmitStart} onClick={() => void handleStatusAction('start')} style={secondaryCtaStyle(isSavingStatus || !canSubmitStart)}>
                <Icon name="clock" size={16}/> 작업 시작
              </button>
            )}
            {canComplete && (
              <button data-testid="partner-complete-job" disabled={isSavingStatus || !canSubmitComplete} onClick={() => void handleStatusAction('complete')} style={primaryCtaStyle(isSavingStatus || !canSubmitComplete)}>
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
          {footerHelpText}
        </div>
      </div>
      <PhotoLightbox
        photos={lightboxPhotos}
        openPhotoId={openPhotoId}
        onOpenPhoto={setOpenPhotoId}
        onClose={() => setOpenPhotoId(null)}
      />
    </div>
  );
}

function formatJobAddress(job) {
  return [stripPostalCode(job.customer_address), job.customer_address_detail].filter(Boolean).join(' ');
}

function stripPostalCode(value) {
  return String(value || '')
    .replace(/^\s*\(?\d{5}\)?\s*/, '')
    .replace(/\s*\(\d{5}\)\s*/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function readInitialPartnerJobId() {
  if (typeof window === 'undefined') {
    return null;
  }
  return new URLSearchParams(window.location.search).get('job');
}

function PartnerJobList({ jobs, onSelect, onReload = undefined }) {
  // 3-1: 로그인 직후 기본으로 '예정' 리스트가 보이도록 한다(전체보기 버튼은 필터 상태에서 상단 상시 노출).
  const [filter, setFilter] = React.useState('upcoming');
  const toggleFilter = (key) => setFilter((current) => (current === key ? null : key));
  const visibleJobs = React.useMemo(() => {
    const base = filter ? jobs.filter((job) => jobBucket(job.status) === filter) : jobs;
    // 3-2: '완료' 탭은 최근(방문일 늦은) 순으로 보여준다. 예정/진행은 백엔드 기본 오름차순 유지.
    if (filter === 'done') {
      return [...base].sort((a, b) => scheduledSortValue(b) - scheduledSortValue(a));
    }
    return base;
  }, [jobs, filter]);

  return (
    <div data-testid="partner-jobs-page" style={{ height: '100%', background: '#f4f6f8', overflow: 'auto', padding: 14 }}>
      <PartnerHomeHero jobs={jobs} activeFilter={filter} onToggleFilter={toggleFilter} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <h2 style={{ margin: 0, fontSize: 16.5, fontWeight: 800 }}>
          {filter ? `${BUCKET_LABELS[filter]} 작업` : '내 작업'}
          {jobs.length > 0 && (
            <span style={{ marginLeft: 6, fontSize: 13, fontWeight: 600, color: 'var(--text-tertiary)' }}>{visibleJobs.length}건</span>
          )}
        </h2>
        <div style={{ flex: 1 }} />
        {filter && (
          <button type="button" onClick={() => setFilter(null)} style={{ height: 32, padding: '0 11px', borderRadius: 8, border: '1px solid var(--border)', background: '#fff', color: 'var(--text-secondary)', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
            전체 보기
          </button>
        )}
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
      ) : visibleJobs.length === 0 ? (
        <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 12, padding: '26px 20px', textAlign: 'center', color: 'var(--text-tertiary)' }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>{BUCKET_LABELS[filter]} 상태인 작업이 없어요</div>
          <button type="button" onClick={() => setFilter(null)} style={{ height: 36, padding: '0 16px', borderRadius: 9, border: '1px solid var(--brand)', background: '#fff', color: 'var(--brand)', fontSize: 12.5, fontWeight: 700, cursor: 'pointer' }}>
            전체 보기
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 10 }}>
          {visibleJobs.map((job) => (
            <button key={job.id} data-testid={`partner-job-row-${job.id}`} onClick={() => onSelect(job.id)} style={{ textAlign: 'left', background: '#fff', border: '1px solid var(--border)', borderRadius: 10, padding: 14, cursor: 'pointer' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <PartnerStatusBadge status={job.status}/>
                {job.is_recurring && <span data-testid="partner-recurring-badge"><Badge tone="brand">정기</Badge></span>}
                <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-tertiary)' }}>{formatKoreanDate(job.scheduled_date)}</span>
              </div>
              <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>{job.service_name}</div>
              <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.45 }}>{formatJobAddress(job)}</div>
              {/* 3-3: 리스트에서 고객 성함/연락처를 바로 확인할 수 있게 노출한다. */}
              <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, flexWrap: 'wrap' }}>
                <Icon name="user" size={12} color="var(--text-tertiary)" />
                <span style={{ fontWeight: 600, color: 'var(--text)' }}>{job.customer_name} 님</span>
                {job.customer_phone && (
                  <span className="mono" style={{ color: 'var(--text-tertiary)' }}>· {formatPhone(job.customer_phone)}</span>
                )}
              </div>
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

function PartnerHomeHero({ jobs, activeFilter = null, onToggleFilter = undefined }) {
  const auth = useAuth();
  const summary = summarizeJobs(jobs);
  const manager = (auth.user?.name || '').trim();
  const handleToggle = (key) => onToggleFilter && onToggleFilter(key);
  return (
    <div
      data-testid="partner-home-hero"
      style={{
        background: 'linear-gradient(135deg, rgba(255,255,255,0.16), rgba(0,0,0,0.10)), var(--brand)',
        borderRadius: 16,
        padding: '16px 16px 14px',
        marginBottom: 14,
        color: '#fff',
        boxShadow: '0 8px 20px rgba(15,23,42,0.16)',
      }}
    >
      <div style={{ fontSize: 13.5, fontWeight: 700 }}>
        {greetingPrefix()}{manager ? `, ${manager}님` : ''}
      </div>
      <div style={{ fontSize: 11.5, opacity: 0.85, display: 'flex', alignItems: 'center', gap: 5, marginTop: 5 }}>
        <Icon name="calendar" size={12} color="#fff" /> {todayLabel()}
      </div>
      <div style={{ fontSize: 16.5, fontWeight: 800, marginTop: 6, letterSpacing: 0 }}>
        {heroHeadline(jobs, summary)}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 13 }}>
        <HeroStat label="예정" value={summary.upcoming} active={activeFilter === 'upcoming'} onClick={() => handleToggle('upcoming')} />
        <HeroStat label="진행" value={summary.inProgress} active={activeFilter === 'inProgress'} onClick={() => handleToggle('inProgress')} />
        <HeroStat label="완료" value={summary.done} active={activeFilter === 'done'} onClick={() => handleToggle('done')} />
      </div>
    </div>
  );
}

function HeroStat({ label, value, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        flex: 1,
        border: active ? '1.5px solid #fff' : '1.5px solid transparent',
        background: active ? 'rgba(255,255,255,0.30)' : 'rgba(255,255,255,0.16)',
        color: '#fff',
        borderRadius: 11,
        padding: '9px 6px',
        textAlign: 'center',
        cursor: 'pointer',
      }}
    >
      <div style={{ fontSize: 19, fontWeight: 800, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 11, opacity: 0.95, marginTop: 4 }}>{label}</div>
    </button>
  );
}

const BUCKET_LABELS = { upcoming: '예정', inProgress: '진행 중', done: '완료' };
const DONE_BUCKET_STATUSES = ['사진검수대기', '고객전달필요', '고객전달완료', '서비스완료'];

function jobBucket(status) {
  if (status === '작업진행') {
    return 'inProgress';
  }
  if (DONE_BUCKET_STATUSES.includes(status)) {
    return 'done';
  }
  return 'upcoming';
}

function scheduledSortValue(job) {
  const date = parseDateValue(job?.scheduled_date);
  return date ? date.getTime() : -Infinity;
}

function summarizeJobs(jobs) {
  const summary = { upcoming: 0, inProgress: 0, done: 0 };
  for (const job of jobs) {
    summary[jobBucket(job.status)] += 1;
  }
  return summary;
}

function heroHeadline(jobs, summary) {
  if (jobs.length === 0) {
    return '오늘은 배정된 작업이 없어요';
  }
  if (summary.inProgress > 0) {
    return `진행 중인 작업 ${summary.inProgress}건`;
  }
  const todayCount = jobs.filter((job) => isToday(job.scheduled_date)).length;
  if (todayCount > 0) {
    return `오늘 방문 예정 ${todayCount}건`;
  }
  return `예정된 작업 ${summary.upcoming}건`;
}

function isToday(value) {
  const date = parseDateValue(value);
  if (!date) {
    return false;
  }
  const now = new Date();
  return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate();
}

function greetingPrefix() {
  const hour = new Date().getHours();
  if (hour < 12) {
    return '좋은 아침이에요';
  }
  if (hour < 18) {
    return '안녕하세요';
  }
  return '오늘도 수고하셨어요';
}

function todayLabel() {
  const now = new Date();
  const weekday = ['일', '월', '화', '수', '목', '금', '토'][now.getDay()];
  return `${now.getMonth() + 1}월 ${now.getDate()}일 ${weekday}요일`;
}

function EvidenceChecklist({ hasBeforePhoto, hasAfterPhoto, hasSignature, canComplete, startedAt, completedAt }) {
  const rows = [
    { key: 'before', label: '비포 사진', done: hasBeforePhoto },
    { key: 'after', label: '애프터 사진', done: hasAfterPhoto },
    { key: 'signature', label: '고객 서명', done: hasSignature },
  ];

  return (
    <Panel>
      <SectionLabel>작업 증빙</SectionLabel>
      <div style={{ display: 'grid', gap: 6 }}>
        {startedAt && <EvidenceRow label="진입시간" value={formatKoreanDateTime(startedAt)} done />}
        {completedAt && <EvidenceRow label="완료시간" value={formatKoreanDateTime(completedAt)} done />}
        {rows.map((row) => (
          <EvidenceRow
            key={row.key}
            label={row.label}
            value={row.done ? '완료' : canComplete ? '필요' : '대기'}
            done={row.done}
          />
        ))}
      </div>
    </Panel>
  );
}

function EvidenceRow({ label, value, done }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 26 }}>
      <Badge tone={done ? 'success' : 'warn'}>{done ? '완료' : '필요'}</Badge>
      <span style={{ flex: 1, fontSize: 12.5, color: 'var(--text)', fontWeight: 600 }}>{label}</span>
      <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>{value}</span>
    </div>
  );
}

function PhotoPanel({
  title,
  tone,
  photos,
  onCapture = undefined,
  onPick = undefined,
  disabled,
  isUploading = false,
  onOpenPhoto,
  showUpload = true,
  canDelete = false,
  deletingPhotoId = null,
  onDeletePhoto = undefined,
}) {
  const uploadLabel = isUploading ? '업로드 중' : disabled ? '잠김' : '촬영';

  return (
    <Panel>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{title}</span>
        <Badge tone={tone}>{photos.length}장</Badge>
        <div style={{ flex: 1 }}/>
        {showUpload && (
          <button onClick={onPick} disabled={disabled} style={{ height: 26, padding: '0 10px', border: 'none', borderRadius: 6, background: tone === 'success' ? 'var(--success-bg)' : 'var(--brand-bg)', color: tone === 'success' ? 'var(--success-fg)' : 'var(--brand)', fontSize: 12, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 4, cursor: disabled ? 'default' : 'pointer' }}>
            <Icon name="image" size={12}/> 앨범
          </button>
        )}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
        {photos.map((photo, index) => (
          <div
            key={photo.id || index}
            style={{
              position: 'relative',
              aspectRatio: '1',
              borderRadius: 6,
              contentVisibility: 'auto',
              containIntrinsicSize: '72px 72px',
            }}
          >
            <button
              type="button"
              data-testid={`partner-photo-thumb-${photo.id}`}
              aria-label={`${title} ${index + 1} 크게 보기`}
              onClick={() => onOpenPhoto(photo.id)}
              style={{ width: '100%', height: '100%', margin: 0, padding: 0, border: '1px solid var(--border)', position: 'relative', overflow: 'hidden', borderRadius: 6, background: 'var(--bg-muted)', cursor: 'zoom-in' }}
            >
              <PartnerPhotoImage photo={photo} alt={photo.file_name || `${title} ${index + 1}`} />
              <span style={{ position: 'absolute', left: 4, bottom: 4, maxWidth: 'calc(100% - 8px)', height: 16, padding: '0 4px', borderRadius: 4, background: 'rgba(15,23,42,0.78)', color: '#fff', fontSize: 9, fontWeight: 700, display: 'inline-flex', alignItems: 'center' }}>
                {index + 1}
              </span>
            </button>
            {canDelete && photo.photo_source !== 'customer_as' && (
              <button
                type="button"
                data-testid={`partner-photo-delete-${photo.id}`}
                aria-label={`${title} ${index + 1} 삭제`}
                disabled={deletingPhotoId === photo.id}
                onClick={() => onDeletePhoto?.(photo)}
                style={{ position: 'absolute', top: -5, right: -5, width: 24, height: 24, borderRadius: 999, border: '1px solid rgba(15,23,42,0.12)', background: '#fff', color: 'var(--danger-fg)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 8px rgba(15,23,42,0.16)', cursor: deletingPhotoId === photo.id ? 'default' : 'pointer' }}
              >
                <Icon name="x" size={13}/>
              </button>
            )}
          </div>
        ))}
        {showUpload && (
          <button onClick={onCapture} disabled={disabled} style={{ aspectRatio: '1', border: '1.5px dashed var(--border-strong)', borderRadius: 6, background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: disabled ? 'default' : 'pointer', flexDirection: 'column', gap: 2, color: 'var(--text-tertiary)' }}>
            <Icon name="camera" size={16}/>
            <span style={{ fontSize: 9.5 }}>{uploadLabel}</span>
          </button>
        )}
      </div>
    </Panel>
  );
}

function PartnerPhotoImage({ photo, alt }) {
  return (
    <ProtectedApiImage
      src={photo.file_url}
      alt={alt}
      loading="lazy"
      style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
      placeholderText="로딩"
      placeholderStyle={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', fontSize: 9, fontWeight: 700 }}
    />
  );
}

function isPartnerFieldActionReady(job) {
  return job.status !== '고객확인필요' || Boolean(job.as_requested);
}

function partnerFooterHelpText(status, asRequested = false) {
  if (status === '고객확인필요') {
    if (!asRequested) {
      return '운영팀이 AS 접수를 확인하면 작업 시작과 사진 등록이 열립니다.';
    }
    return 'AS 요청을 확인한 뒤 비포 사진을 올리고 작업을 시작하세요.';
  }
  if (DONE_BUCKET_STATUSES.includes(status)) {
    return '작업 완료 처리가 기록되었습니다.';
  }
  return '작업완료 시 미수금이 있으면 고객에게 잔금 안내가 자동 발송됩니다.';
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
  return <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: 0, marginBottom: 6 }}>{children}</div>;
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
    customerAs: [],
  };

  for (const photo of photos) {
    if (photo.photo_source === 'customer_as') {
      groups.customerAs.push(photo);
    } else if (photo.photo_type === 'before') {
      groups.before.push(photo);
    } else if (photo.photo_type === 'after') {
      groups.after.push(photo);
    } else {
      groups.etc.push(photo);
    }
  }

  return groups;
}

function filterCurrentEvidencePhotos(job) {
  if (!job?.photos) {
    return [];
  }
  if (!job.as_requested || !job.as_requested_at) {
    return job.photos;
  }
  const requestedAt = Date.parse(job.as_requested_at);
  if (Number.isNaN(requestedAt)) {
    return job.photos;
  }
  return job.photos.filter((photo) => {
    const createdAt = Date.parse(photo.created_at || '');
    return !Number.isNaN(createdAt) && createdAt >= requestedAt;
  });
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

function toPhotoDeleteErrorMessage(error) {
  if (error instanceof ApiError) {
    if (error.detail === 'invalid_status_for_delete') {
      return '현재 작업 상태에서는 사진을 삭제할 수 없습니다.';
    }
    if (error.detail === 'photo_delete_not_allowed') {
      return '이 사진은 협력사 화면에서 삭제할 수 없습니다.';
    }
    if (error.detail === 'photo_not_found') {
      return '삭제할 사진을 찾을 수 없습니다.';
    }
  }
  return '사진을 삭제하지 못했습니다.';
}

function photoUploadLockMessage(status, asRequested = false) {
  if (status === '취소') {
    return '취소된 작업이라 사진을 업로드할 수 없습니다.';
  }
  if (status === '고객확인필요' && !asRequested) {
    return '운영팀이 AS 접수를 확인하면 비포/애프터 사진 등록을 사용할 수 있습니다.';
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
  if (status === '고객확인필요') {
    return '확인 필요';
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
  if (status === '고객확인필요') {
    return 'warn';
  }
  if (status === '작업진행') {
    return 'info';
  }
  return 'neutral';
}

function getPartnerStatusLock(status, asRequested = false) {
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
  if (status === '고객확인필요' && !asRequested) {
    return {
      icon: 'lock',
      tone: 'warn',
      title: '운영팀 확인 대기',
      description: '고객 AS 접수 건입니다. 운영팀 접수완료 후 작업 액션을 사용할 수 있습니다.',
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
