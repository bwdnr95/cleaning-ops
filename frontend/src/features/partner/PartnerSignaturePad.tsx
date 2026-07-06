import React from 'react';
import { Icon } from '../../components/common/ui';

type PartnerSignaturePadProps = {
  readonly value: string;
  readonly disabled?: boolean;
  readonly onChange: (value: string) => void;
};

type CanvasDrawEvent = React.PointerEvent<HTMLCanvasElement> | React.MouseEvent<HTMLCanvasElement>;

export function PartnerSignaturePad({ value, disabled = false, onChange }: PartnerSignaturePadProps) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const isDrawingRef = React.useRef(false);
  const didDrawRef = React.useRef(false);
  const lastPointRef = React.useRef<{ readonly x: number; readonly y: number } | null>(null);

  const resetCanvas = React.useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.floor(canvas.clientWidth * ratio);
    canvas.height = Math.floor(132 * ratio);
    const context = canvas.getContext('2d');
    if (!context) return;
    context.scale(ratio, ratio);
    context.lineCap = 'round';
    context.lineJoin = 'round';
    context.lineWidth = 2.4;
    const colors = getSignatureCanvasColors();
    context.strokeStyle = colors.stroke;
    context.fillStyle = colors.background;
    context.fillRect(0, 0, canvas.clientWidth, 132);
  }, []);

  React.useEffect(() => {
    resetCanvas();
  }, [resetCanvas]);

  React.useEffect(() => {
    if (!value) {
      resetCanvas();
    }
  }, [resetCanvas, value]);

  const pointFromEvent = (event: CanvasDrawEvent) => {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
  };

  function markSignatureChanged(canvas: HTMLCanvasElement) {
    onChange(canvas.toDataURL('image/png'));
  }

  const beginDrawing = (event: CanvasDrawEvent) => {
    if (disabled) return;
    if ('pointerId' in event) {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    isDrawingRef.current = true;
    didDrawRef.current = false;
    lastPointRef.current = pointFromEvent(event);
  };

  const continueDrawing = (event: CanvasDrawEvent) => {
    if (!isDrawingRef.current || disabled) return;
    const context = event.currentTarget.getContext('2d');
    const previous = lastPointRef.current;
    if (!context || !previous) return;
    const next = pointFromEvent(event);
    if (Math.abs(next.x - previous.x) < 0.5 && Math.abs(next.y - previous.y) < 0.5) {
      return;
    }
    context.beginPath();
    context.moveTo(previous.x, previous.y);
    context.lineTo(next.x, next.y);
    context.stroke();
    didDrawRef.current = true;
    lastPointRef.current = next;
  };

  const finishDrawing = (event: CanvasDrawEvent) => {
    if (!isDrawingRef.current) return;
    isDrawingRef.current = false;
    lastPointRef.current = null;
    if (didDrawRef.current) {
      markSignatureChanged(event.currentTarget);
    }
    didDrawRef.current = false;
  };

  const clearSignature = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    resetCanvas();
    onChange('');
  };

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <div
        style={{
          border: `1px solid ${value ? 'var(--success-fg)' : 'var(--border)'}`,
          borderRadius: 8,
          background: 'var(--surface)',
          overflow: 'hidden',
        }}
      >
        <canvas
          ref={canvasRef}
          data-testid="partner-signature-canvas"
          aria-label="고객 서명 입력"
          style={{
            display: 'block',
            width: '100%',
            height: 132,
            touchAction: 'none',
            cursor: disabled ? 'default' : 'crosshair',
          }}
          onPointerDown={beginDrawing}
          onPointerMove={continueDrawing}
          onPointerUp={finishDrawing}
          onPointerCancel={finishDrawing}
          onMouseDown={beginDrawing}
          onMouseMove={continueDrawing}
          onMouseUp={finishDrawing}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
        <span style={{ fontSize: 11.5, color: value ? 'var(--success-fg)' : 'var(--text-tertiary)', fontWeight: value ? 700 : 500 }}>
          {value ? '서명이 입력되었습니다.' : '고객님께 직접 서명을 받아주세요.'}
        </span>
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          disabled={disabled || !value}
          onClick={clearSignature}
          style={{ height: 28, padding: '0 8px' }}
        >
          <Icon name="x" size={12}/> 지우기
        </button>
      </div>
    </div>
  );
}

function getSignatureCanvasColors() {
  const rootStyle = getComputedStyle(document.documentElement);
  return {
    stroke: rootStyle.getPropertyValue('--text').trim() || '#0f172a',
    background: rootStyle.getPropertyValue('--surface').trim() || '#ffffff',
  };
}
