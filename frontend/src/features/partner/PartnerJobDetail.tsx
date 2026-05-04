import React from 'react';
import { Avatar, Badge, Icon, StatusBadge } from '../../components/common/ui';
import { listPartnerJobs } from '../../api/partner';
import { uploadPartnerJobPhoto } from '../../api/photos';
import { useApiResource } from '../../api/useApiResource';

// Partner mobile — job detail + photo upload (single screen, mobile-first)

export function PartnerJobDetail() {
  const jobs = useApiResource(listPartnerJobs);
  const job = jobs.data?.[0];
  const [befores, setBefores] = React.useState([1, 2, 3, 4, 5]);
  const [afters, setAfters] = React.useState([1, 2, 3]);
  const [uploadingIdx] = React.useState(2);
  const [uploadError, setUploadError] = React.useState(null);
  const [isUploading, setIsUploading] = React.useState(false);
  const beforeInputRef = React.useRef<HTMLInputElement | null>(null);
  const afterInputRef = React.useRef<HTMLInputElement | null>(null);

  const handlePhotoSelected = async (photoType, event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !job) {
      return;
    }

    setUploadError(null);
    setIsUploading(true);
    try {
      const nextNo = photoType === 'before' ? befores.length + 1 : afters.length + 1;
      await uploadPartnerJobPhoto(job.id, {
        photoType,
        file,
      });
      if (photoType === 'before') {
        setBefores([...befores, nextNo]);
      } else {
        setAfters([...afters, nextNo]);
      }
    } catch {
      setUploadError('사진 업로드를 처리하지 못했습니다.');
    } finally {
      setIsUploading(false);
    }
  };

  if (jobs.isLoading) {
    return <PartnerState text="작업을 불러오는 중입니다." />;
  }

  if (jobs.error) {
    return <PartnerState text="작업 목록을 불러오지 못했습니다." tone="danger" />;
  }

  if (!job) {
    return <PartnerState text="배정된 작업이 없습니다." />;
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#f4f6f8', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px 10px',
        background: '#fff',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <button style={{ padding: 0, border: 'none', background: 'transparent', cursor: 'pointer' }}>
            <Icon name="chevronLeft" size={20}/>
          </button>
          <span className="mono" style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{job.id}</span>
          <StatusBadge status={job.status}/>
          <div style={{ flex: 1 }}/>
          <button style={{ padding: 4, border: 'none', background: 'transparent' }}>
            <Icon name="moreHorizontal" size={18}/>
          </button>
        </div>
        <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, letterSpacing: '-0.02em' }}>{job.service_name}</h2>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>{job.size_or_quantity || job.service_detail || '상세 수량 미입력'}</div>
      </div>

      {/* Body */}
      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: 12 }}>
        {/* Quick info card */}
        <div style={{
          background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10,
          border: '1px solid var(--border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, paddingBottom: 10, borderBottom: '1px solid var(--divider)' }}>
            <span style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--info-bg)', color: 'var(--info-fg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="calendar" size={16}/>
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700 }}>{formatKoreanDate(job.scheduled_date)}</div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{job.requested_time || '시간 협의'}</div>
            </div>
            <Badge tone="warn" dot>오늘</Badge>
          </div>

          <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
            <span style={{ width: 16, marginTop: 2 }}><Icon name="mapPin" size={14} color="var(--text-tertiary)"/></span>
            <div style={{ flex: 1, fontSize: 13, lineHeight: 1.5 }}>
              {job.customer_address}<br/>
              <span style={{ color: 'var(--text-tertiary)' }}>{job.service_detail || '현장 상세 정보 없음'}</span>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            <button style={{
              height: 36, border: '1px solid var(--border)', borderRadius: 8,
              background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
              fontSize: 12.5, fontWeight: 500,
            }}>
              <Icon name="mapPin" size={14} color="var(--brand)"/> 지도 열기
            </button>
            <button style={{
              height: 36, border: '1px solid var(--border)', borderRadius: 8,
              background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
              fontSize: 12.5, fontWeight: 500,
            }}>
              <Icon name="phone" size={14} color="var(--success-fg)"/> 고객 전화
            </button>
          </div>
        </div>

        {/* Customer + request */}
        <div style={{ background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 6 }}>고객</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Avatar name={job.customer_name} size={28} tone="brand"/>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13.5, fontWeight: 600 }}>{job.customer_name} 님</div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>{maskPhone(job.customer_phone)}</div>
            </div>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 6 }}>특별 요청</div>
          <div style={{
            padding: 10, background: 'var(--warn-bg)', border: '1px solid var(--warn-border)',
            borderRadius: 8, fontSize: 12.5, lineHeight: 1.5, color: '#78350f',
          }}>
            {job.special_request || '별도 요청 사항이 없습니다.'}
          </div>
        </div>

        {/* Photos */}
        <div style={{ background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>비포 사진</span>
            <Badge tone="neutral">{befores.length}장</Badge>
            <div style={{ flex: 1 }}/>
            <button style={{
              height: 26, padding: '0 10px', border: 'none', borderRadius: 6,
              background: 'var(--brand-bg)', color: 'var(--brand)',
              fontSize: 12, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 4,
            }}>
              <Icon name="plus" size={12}/> 추가
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
            {befores.map((b, i) => (
              <div key={i} className="placeholder-img" style={{ aspectRatio: '1', fontSize: 9, position: 'relative' }}>
                B-{b}
                <span style={{ position: 'absolute', top: 3, right: 3, width: 14, height: 14, borderRadius: '50%', background: 'rgba(0,0,0,0.6)', color: '#fff', fontSize: 9, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>×</span>
              </div>
            ))}
            <input
              ref={beforeInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              capture="environment"
              style={{ display: 'none' }}
              onChange={(event) => void handlePhotoSelected('before', event)}
            />
            <button onClick={() => beforeInputRef.current?.click()} disabled={isUploading} style={{
              aspectRatio: '1', border: '1.5px dashed var(--border-strong)', borderRadius: 6,
              background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: isUploading ? 'default' : 'pointer', flexDirection: 'column', gap: 2, color: 'var(--text-tertiary)',
            }}>
              <Icon name="camera" size={16}/>
              <span style={{ fontSize: 9.5 }}>{isUploading ? '업로드' : '촬영'}</span>
            </button>
          </div>
          {uploadError && <div style={{ marginTop: 8, color: 'var(--danger-fg)', fontSize: 11.5 }}>{uploadError}</div>}
        </div>

        <div style={{ background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>애프터 사진</span>
            <Badge tone="success">{afters.length}장</Badge>
            <div style={{ flex: 1 }}/>
            <button style={{
              height: 26, padding: '0 10px', border: 'none', borderRadius: 6,
              background: 'var(--success-bg)', color: 'var(--success-fg)',
              fontSize: 12, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 4,
            }}>
              <Icon name="plus" size={12}/> 추가
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
            {afters.map((a, i) => (
              <div key={i} className="placeholder-img" style={{ aspectRatio: '1', fontSize: 9 }}>A-{a}</div>
            ))}
            {/* uploading state */}
            <div className="placeholder-img" style={{ aspectRatio: '1', fontSize: 9, position: 'relative', overflow: 'hidden' }}>
              A-{uploadingIdx + 2}
              <div style={{
                position: 'absolute', inset: 0, background: 'rgba(15, 23, 42, 0.5)',
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3,
              }}>
                <span style={{ fontSize: 9, color: '#fff', fontWeight: 600 }}>62%</span>
                <div style={{ width: 36, height: 3, background: 'rgba(255,255,255,0.3)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: '62%', height: '100%', background: '#fff' }}/>
                </div>
              </div>
            </div>
            <input
              ref={afterInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              capture="environment"
              style={{ display: 'none' }}
              onChange={(event) => void handlePhotoSelected('after', event)}
            />
            <button onClick={() => afterInputRef.current?.click()} disabled={isUploading} style={{
              aspectRatio: '1', border: '1.5px dashed var(--border-strong)', borderRadius: 6,
              background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: isUploading ? 'default' : 'pointer', flexDirection: 'column', gap: 2, color: 'var(--text-tertiary)',
            }}>
              <Icon name="camera" size={16}/>
              <span style={{ fontSize: 9.5 }}>{isUploading ? '업로드' : '촬영'}</span>
            </button>
          </div>
        </div>

        {/* Memo */}
        <div style={{ background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 6 }}>작업 메모</div>
          <textarea
            defaultValue="스탠드 1대 필터 교체 권장 (별도 비용 안내드림)."
            style={{
              width: '100%', minHeight: 64, padding: 10,
              border: '1px solid var(--border)', borderRadius: 8,
              fontSize: 13, fontFamily: 'inherit', resize: 'none',
              background: 'var(--bg-subtle)',
            }}/>
        </div>
      </div>

      {/* Sticky bottom CTA */}
      <div style={{
        padding: '10px 14px 12px',
        background: '#fff',
        borderTop: '1px solid var(--border)',
        boxShadow: '0 -4px 12px rgba(15,23,42,0.04)',
      }}>
        <button style={{
          width: '100%', height: 46,
          background: 'var(--brand)', color: '#fff', border: 'none',
          borderRadius: 10, fontSize: 14.5, fontWeight: 700,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          cursor: 'pointer',
        }}>
          <Icon name="check" size={16}/> 작업 완료 처리
        </button>
        <div style={{ textAlign: 'center', fontSize: 10.5, color: 'var(--text-tertiary)', marginTop: 6 }}>
          완료 처리 시 관리자에게 사진 검수 요청이 자동 발송됩니다
        </div>
      </div>
    </div>
  );
}

function PartnerState({ text, tone = 'muted' }) {
  return (
    <div style={{
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 24,
      background: '#f4f6f8',
      color: tone === 'danger' ? 'var(--danger-fg)' : 'var(--text-tertiary)',
      fontSize: 13,
      textAlign: 'center',
    }}>
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
