import { Badge, Icon } from '../../../components/common/ui';
import { formatPhone } from '../../../domain/phone';
import type { AdminMessageChannel } from '../../../api/messages';
import {
  messagePreviewWarningLabel,
} from './OrderDetailFormat';
import type { MessageActionDraft, MessagePreviewData } from './OrderDetailModel';

interface MessagePreviewModalProps {
  readonly draft: MessageActionDraft | null;
  readonly channel: AdminMessageChannel;
  readonly preview: MessagePreviewData | null;
  readonly previewError: string | null;
  readonly isLoading: boolean;
  readonly isSaving: boolean;
  readonly onChannelChange: (channel: AdminMessageChannel) => void;
  readonly onClose: () => void;
  readonly onConfirm: () => void;
}

export function MessagePreviewModal({
  draft,
  channel,
  preview,
  previewError,
  isLoading,
  isSaving,
  onChannelChange,
  onClose,
  onConfirm,
}: MessagePreviewModalProps) {
  if (!draft) {
    return null;
  }

  const warnings = preview?.warnings || [];
  const variables = preview?.kakao_variables ? Object.entries(preview.kakao_variables) : [];
  const isAlimtalk = channel === 'alimtalk';
  const canSend = Boolean(preview && preview.can_send !== false && !previewError && !isLoading && !isSaving);

  return (
    <div
      data-testid="message-preview-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="message-preview-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        background: 'rgba(15, 23, 42, 0.38)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
    >
      <div
        className="card"
        style={{
          width: 'min(640px, 100%)',
          maxHeight: 'min(760px, calc(100vh - 40px))',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div id="message-preview-title" style={{ fontSize: 14, fontWeight: 700 }}>{draft.title}</div>
            <div style={{ marginTop: 3, fontSize: 11.5, color: 'var(--text-tertiary)' }}>
              {preview ? `${preview.recipient_name} · ${formatPhone(preview.recipient_phone)}` : '발송 정보를 확인하는 중입니다.'}
            </div>
          </div>
          <button className="btn btn--ghost btn--sm" onClick={onClose} aria-label="닫기" style={{ padding: '0 6px' }}>
            <Icon name="x" size={14}/>
          </button>
        </div>

        <div className="scroll" style={{ padding: 16, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, marginBottom: 8 }}>발송 채널</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              <button
                data-testid="message-preview-channel-sms"
                className={`btn ${channel === 'sms' ? 'btn--primary' : 'btn--secondary'}`}
                disabled={isLoading || isSaving}
                aria-pressed={channel === 'sms'}
                onClick={() => onChannelChange('sms')}
              >
                SMS
              </button>
              <button
                data-testid="message-preview-channel-alimtalk"
                className={`btn ${channel === 'alimtalk' ? 'btn--primary' : 'btn--secondary'}`}
                disabled={isLoading || isSaving}
                aria-pressed={channel === 'alimtalk'}
                onClick={() => onChannelChange('alimtalk')}
              >
                알림톡
              </button>
            </div>
          </div>

          {previewError && (
            <div
              data-testid="message-preview-error"
              style={{ padding: 10, borderRadius: 6, background: 'var(--danger-bg)', color: 'var(--danger-fg)', fontSize: 12 }}
            >
              {previewError}
            </div>
          )}

          {isLoading ? (
            <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-tertiary)', fontSize: 12 }}>
              미리보기를 불러오는 중입니다.
            </div>
          ) : (
            preview && (
              <>
                {isAlimtalk && (
                  <AlimtalkPreviewMeta preview={preview} variables={variables} />
                )}

                {warnings.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {warnings.map((warning) => (
                      <div
                        key={warning}
                        data-testid="message-preview-warning"
                        style={{ padding: 10, borderRadius: 6, background: 'var(--warn-bg)', color: 'var(--warn-fg)', fontSize: 12 }}
                      >
                        {messagePreviewWarningLabel(warning)}
                      </div>
                    ))}
                  </div>
                )}

                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, marginBottom: 8 }}>
                    {isAlimtalk ? 'SMS fallback 문구' : '발송 문구'}
                  </div>
                  <pre
                    data-testid="message-preview-content"
                    style={{
                      margin: 0,
                      padding: 12,
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      background: 'var(--bg-subtle)',
                      color: 'var(--text)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 11.5,
                      lineHeight: 1.55,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {isAlimtalk ? preview.fallback_sms_content || preview.content : preview.content}
                  </pre>
                </div>
              </>
            )
          )}
        </div>

        <div style={{ padding: 14, borderTop: '1px solid var(--divider)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn btn--ghost" onClick={onClose} disabled={isSaving}>취소</button>
          <button data-testid="message-preview-send" className="btn btn--primary" onClick={onConfirm} disabled={!canSend}>
            <Icon name="send" size={13}/> 발송
          </button>
        </div>
      </div>
    </div>
  );
}

function AlimtalkPreviewMeta({
  preview,
  variables,
}: {
  readonly preview: MessagePreviewData;
  readonly variables: readonly [string, string | number | boolean | null][];
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <Badge tone={preview.kakao_channel_id_configured ? 'success' : 'warn'}>
          Channel ID {preview.kakao_channel_id_configured ? '설정됨' : '미설정'}
        </Badge>
        <Badge tone={preview.kakao_template_configured ? 'success' : 'warn'}>
          템플릿 {preview.kakao_template_configured ? '설정됨' : '미설정'}
        </Badge>
        <Badge tone={preview.fallback_sms_enabled ? 'info' : 'neutral'}>
          SMS fallback {preview.fallback_sms_enabled ? 'ON' : 'OFF'}
        </Badge>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, fontSize: 12 }}>
        <span style={{ color: 'var(--text-tertiary)' }}>템플릿 ID</span>
        <span data-testid="message-preview-template-id" className="mono" style={{ color: 'var(--text)' }}>
          {preview.kakao_template_id || '미설정'}
        </span>
      </div>
      {variables.length > 0 && (
        <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
          {variables.map(([key, value]) => (
            <div key={key} style={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 8, padding: '8px 10px', borderBottom: '1px solid var(--divider)', fontSize: 11.5 }}>
              <span className="mono" style={{ color: 'var(--text-tertiary)', minWidth: 0 }}>{key}</span>
              <span style={{ minWidth: 0, wordBreak: 'break-word' }}>{String(value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
