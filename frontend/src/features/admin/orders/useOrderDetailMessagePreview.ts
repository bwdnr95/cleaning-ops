import React from 'react';

import type { AdminMessageChannel } from '../../../api/messages';
import { previewAdminMessage, sendAdminMessage } from '../../../api/messages';
import {
  isMessageFailure,
  isMessagePending,
  messageChannelLabel,
  messageProviderErrorText,
  messageStatusLabel,
  toActionErrorMessage,
} from './OrderDetailFormat';
import type { AdminOrderDetail, MessageActionDraft, MessagePreviewData } from './OrderDetailModel';

interface UseOrderDetailMessagePreviewInput {
  readonly order: AdminOrderDetail | null;
  readonly reloadOrder: () => void;
  readonly runAction: (action: () => Promise<void>) => Promise<void>;
  readonly setNotice: (notice: string) => void;
  readonly setError: (error: string) => void;
}

export function useOrderDetailMessagePreview({
  order,
  reloadOrder,
  runAction,
  setNotice,
  setError,
}: UseOrderDetailMessagePreviewInput) {
  const defaultChannel: AdminMessageChannel = 'alimtalk';
  const [messageDraft, setMessageDraft] = React.useState<MessageActionDraft | null>(null);
  const [messagePreviewChannel, setMessagePreviewChannel] = React.useState<AdminMessageChannel>(defaultChannel);
  const [messagePreviewData, setMessagePreviewData] = React.useState<MessagePreviewData | null>(null);
  const [messagePreviewError, setMessagePreviewError] = React.useState<string | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = React.useState(false);

  React.useEffect(() => {
    if (!messageDraft) {
      setMessagePreviewChannel(defaultChannel);
    }
  }, [defaultChannel, messageDraft]);

  const fetchMessagePreview = async (draft: MessageActionDraft, channel: AdminMessageChannel) => {
    if (!order) {
      return null;
    }
    setIsPreviewLoading(true);
    setMessagePreviewError(null);
    try {
      const preview = await previewAdminMessage(order.id, draft.messageType, draft.recipientType, channel);
      setMessagePreviewData(preview);
      return preview;
    } catch (requestError) {
      const actionError = toActionErrorMessage(requestError);
      setMessagePreviewData(null);
      setMessagePreviewError(actionError);
      throw requestError;
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const openMessagePreview = async (draft: MessageActionDraft): Promise<boolean> => {
    setError('');
    setNotice('');
    setMessageDraft(draft);
    const initialChannel = draft.initialChannel || defaultChannel;
    setMessagePreviewChannel(initialChannel);
    setMessagePreviewData(null);
    setMessagePreviewError(null);
    try {
      await fetchMessagePreview(draft, initialChannel);
      return true;
    } catch (requestError) {
      setMessageDraft(null);
      setError(toActionErrorMessage(requestError));
      return false;
    }
  };

  const handlePreviewChannelChange = async (channel: AdminMessageChannel) => {
    if (!messageDraft || channel === messagePreviewChannel) {
      return;
    }
    setMessagePreviewChannel(channel);
    try {
      await fetchMessagePreview(messageDraft, channel);
    } catch {
      return;
    }
  };

  const closeMessagePreview = () => {
    setMessageDraft(null);
    setMessagePreviewData(null);
    setMessagePreviewError(null);
    setMessagePreviewChannel(defaultChannel);
  };

  const handleConfirmMessageSend = async () => {
    if (!messageDraft || !order) {
      return;
    }
    await runAction(async () => {
      const sent = await sendAdminMessage(
        order.id,
        messageDraft.messageType,
        messageDraft.recipientType,
        messagePreviewChannel,
      );
      closeMessagePreview();
      const channelLabel = messageChannelLabel(sent.channel || messagePreviewChannel);
      if (isMessageFailure(sent.status)) {
        setError(`${messageDraft.title} 발송 결과: ${messageStatusLabel(sent.status)} (${channelLabel}) - ${messageProviderErrorText(sent)}`);
      } else if (isMessagePending(sent.status)) {
        setError(`${messageDraft.title} 결과를 확인 중입니다. SOLAPI 콘솔 확인 전에는 재발송하지 마세요. (${channelLabel})`);
      } else {
        setNotice(`${messageDraft.successText} (${channelLabel})`);
      }
      reloadOrder();
    });
  };

  return {
    messageDraft,
    messagePreviewChannel,
    messagePreviewData,
    messagePreviewError,
    isPreviewLoading,
    openMessagePreview,
    handlePreviewChannelChange,
    closeMessagePreview,
    handleConfirmMessageSend,
  };
}
