import React from 'react';
import { Avatar, Badge, Icon } from '../../components/common/ui';
import { completePartnerJob, getPartnerJob, listPartnerJobs, startPartnerJob } from '../../api/partner';
import { uploadPartnerJobPhoto } from '../../api/photos';
import { useApiResource } from '../../api/useApiResource';

export function PartnerJobDetail() {
  const [selectedJobId, setSelectedJobId] = React.useState(null);
  const [beforePhotos, setBeforePhotos] = React.useState([]);
  const [afterPhotos, setAfterPhotos] = React.useState([]);
  const [uploadError, setUploadError] = React.useState(null);
  const [statusError, setStatusError] = React.useState(null);
  const [isUploading, setIsUploading] = React.useState(false);
  const [isSavingStatus, setIsSavingStatus] = React.useState(false);
  const beforeInputRef = React.useRef<HTMLInputElement | null>(null);
  const afterInputRef = React.useRef<HTMLInputElement | null>(null);

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

  React.useEffect(() => {
    setBeforePhotos([]);
    setAfterPhotos([]);
    setUploadError(null);
    setStatusError(null);
  }, [selectedJobId]);

  const refreshFlow = () => {
    jobs.reload();
    detail.reload();
  };

  const handlePhotoSelected = async (photoType, event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !job) {
      return;
    }

    setUploadError(null);
    setIsUploading(true);
    try {
      const uploaded = await uploadPartnerJobPhoto(job.id, { photoType, file });
      if (photoType === 'before') {
        setBeforePhotos((current) => [...current, uploaded]);
      } else {
        setAfterPhotos((current) => [...current, uploaded]);
      }
      refreshFlow();
    } catch {
      setUploadError('사진 업로드를 처리하지 못했습니다.');
    } finally {
      setIsUploading(false);
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
    } catch {
      setStatusError('작업 상태를 변경하지 못했습니다.');
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
    return <PartnerJobList jobs={jobs.data || []} onSelect={setSelectedJobId} />;
  }

  if (detail.isLoading && !selectedFromList) {
    return <PartnerState text="작업 상세를 불러오는 중입니다." />;
  }

  if (detail.error || !job) {
    return <PartnerState text="작업 상세를 불러오지 못했습니다." tone="danger" />;
  }

  const canStart = job.status !== '작업진행' && job.status !== '사진검수대기';

  return (
    <div data-testid="partner-job-detail-page" style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#f4f6f8', overflow: 'hidden' }}>
      <div style={{ padding: '12px 16px 10px', background: '#fff', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <button onClick={() => setSelectedJobId(null)} style={{ padding: 0, border: 'none', background: 'transparent', cursor: 'pointer' }}>
            <Icon name="chevronLeft" size={20}/>
          </button>
          <span className="mono" style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{job.id}</span>
          <PartnerStatusBadge status={job.status}/>
        </div>
        <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>{job.service_name}</h2>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>{job.size_or_quantity || job.service_detail || '상세 수량 미입력'}</div>
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
            {job.customer_address}<br/>
            <span style={{ color: 'var(--text-tertiary)' }}>{job.service_detail || '현장 상세 정보 없음'}</span>
          </InfoRow>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            <ActionButton icon="mapPin" label="지도 열기" href={`https://map.naver.com/p/search/${encodeURIComponent(job.customer_address)}`} />
            <ActionButton icon="phone" label="고객 전화" href={job.customer_phone ? `tel:${digitsOnly(job.customer_phone)}` : undefined} />
          </div>
        </Panel>

        <Panel>
          <SectionLabel>고객</SectionLabel>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Avatar name={job.customer_name} size={28} tone="brand"/>
            <div>
              <div style={{ fontSize: 13.5, fontWeight: 600 }}>{job.customer_name} 님</div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>{maskPhone(job.customer_phone)}</div>
            </div>
          </div>
          <SectionLabel>특별 요청</SectionLabel>
          <div style={{ padding: 10, background: 'var(--warn-bg)', border: '1px solid var(--warn-border)', borderRadius: 8, fontSize: 12.5, lineHeight: 1.5, color: '#78350f' }}>
            {job.special_request || '별도 요청 사항이 없습니다.'}
          </div>
        </Panel>

        <PhotoPanel
          title="비포 사진"
          tone="neutral"
          prefix="B"
          photos={beforePhotos}
          onAdd={() => beforeInputRef.current?.click()}
          disabled={isUploading}
        />
        <input ref={beforeInputRef} data-testid="partner-before-photo-input" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" style={{ display: 'none' }} onChange={(event) => void handlePhotoSelected('before', event)} />

        <PhotoPanel
          title="애프터 사진"
          tone="success"
          prefix="A"
          photos={afterPhotos}
          onAdd={() => afterInputRef.current?.click()}
          disabled={isUploading}
        />
        <input ref={afterInputRef} data-testid="partner-after-photo-input" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" style={{ display: 'none' }} onChange={(event) => void handlePhotoSelected('after', event)} />
        {uploadError && <div style={{ margin: '-2px 2px 10px', color: 'var(--danger-fg)', fontSize: 11.5 }}>{uploadError}</div>}
      </div>

      <div style={{ padding: '10px 14px 12px', background: '#fff', borderTop: '1px solid var(--border)', boxShadow: '0 -4px 12px rgba(15,23,42,0.04)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: canStart ? '1fr 1fr' : '1fr', gap: 8 }}>
          {canStart && (
            <button data-testid="partner-start-job" disabled={isSavingStatus} onClick={() => void handleStatusAction('start')} style={secondaryCtaStyle(isSavingStatus)}>
              <Icon name="clock" size={16}/> 작업 시작
            </button>
          )}
          <button data-testid="partner-complete-job" disabled={isSavingStatus} onClick={() => void handleStatusAction('complete')} style={primaryCtaStyle(isSavingStatus)}>
            <Icon name="check" size={16}/> 작업 완료
          </button>
        </div>
        {statusError && <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--danger-fg)', marginTop: 6 }}>{statusError}</div>}
        <div style={{ textAlign: 'center', fontSize: 10.5, color: 'var(--text-tertiary)', marginTop: 6 }}>
          사진 업로드와 완료 처리는 운영팀 확인 단계로 넘어갑니다
        </div>
      </div>
    </div>
  );
}

function PartnerJobList({ jobs, onSelect }) {
  if (jobs.length === 0) {
    return <PartnerState text="배정된 작업이 없습니다." />;
  }

  return (
    <div data-testid="partner-jobs-page" style={{ height: '100%', background: '#f4f6f8', overflow: 'auto', padding: 14 }}>
      <div style={{ marginBottom: 14 }}>
        <div className="app-eyebrow">협력사 현장</div>
        <h2 style={{ margin: '2px 0 0', fontSize: 20 }}>내 작업</h2>
      </div>
      <div style={{ display: 'grid', gap: 10 }}>
        {jobs.map((job) => (
          <button key={job.id} data-testid={`partner-job-row-${job.id}`} onClick={() => onSelect(job.id)} style={{ textAlign: 'left', background: '#fff', border: '1px solid var(--border)', borderRadius: 10, padding: 14, cursor: 'pointer' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <PartnerStatusBadge status={job.status}/>
              <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-tertiary)' }}>{formatKoreanDate(job.scheduled_date)}</span>
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>{job.service_name}</div>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.45 }}>{job.customer_address}</div>
            <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--brand)', fontSize: 12.5, fontWeight: 700 }}>
              상세 보기 <Icon name="chevronRight" size={14}/>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function PhotoPanel({ title, tone, prefix, photos, onAdd, disabled }) {
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
          <div key={photo.id || index} className="placeholder-img" style={{ aspectRatio: '1', fontSize: 9 }}>
            {prefix}-{index + 1}
          </div>
        ))}
        <button onClick={onAdd} disabled={disabled} style={{ aspectRatio: '1', border: '1.5px dashed var(--border-strong)', borderRadius: 6, background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: disabled ? 'default' : 'pointer', flexDirection: 'column', gap: 2, color: 'var(--text-tertiary)' }}>
          <Icon name="camera" size={16}/>
          <span style={{ fontSize: 9.5 }}>{disabled ? '업로드 중' : '촬영'}</span>
        </button>
      </div>
    </Panel>
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

function PartnerState({ text, tone = 'muted' }) {
  return (
    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, background: '#f4f6f8', color: tone === 'danger' ? 'var(--danger-fg)' : 'var(--text-tertiary)', fontSize: 13, textAlign: 'center' }}>
      {text}
    </div>
  );
}

function formatKoreanDate(value) {
  if (!value) {
    return '일정 미정';
  }

  const date = new Date(`${value}T00:00:00`);
  const weekday = ['일', '월', '화', '수', '목', '금', '토'][date.getDay()];
  return `${date.getMonth() + 1}월 ${date.getDate()}일 ${weekday}요일`;
}

function maskPhone(phone) {
  if (!phone) {
    return '';
  }
  const digits = phone.replace(/\D/g, '');
  if (digits.length < 8) {
    return phone;
  }
  return `${digits.slice(0, 3)}-${digits.slice(3, 4)}***-${digits.slice(-4)}`;
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

function digitsOnly(value) {
  return String(value || '').replace(/\D/g, '');
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
