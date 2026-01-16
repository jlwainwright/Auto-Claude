import { useState, useEffect } from 'react';
import { Bell, Loader2, CheckCircle2, AlertCircle, Hash, Send, MessageSquare, RefreshCw } from 'lucide-react';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { Switch } from '../../ui/switch';
import { Separator } from '../../ui/separator';
import { Button } from '../../ui/button';

// Debug logging
const DEBUG = process.env.NODE_ENV === 'development' || process.env.DEBUG === 'true';
function debugLog(message: string, data?: unknown) {
  if (DEBUG) {
    if (data !== undefined) {
      console.warn(`[SlackIntegration] ${message}`, data);
    } else {
      console.warn(`[SlackIntegration] ${message}`);
    }
  }
}

interface SlackConnectionStatus {
  connected: boolean;
  channelName?: string;
  webhookValid?: boolean;
  error?: string;
}

interface SlackIntegrationProps {
  slackEnabled: boolean;
  slackWebhookUrl?: string;
  slackChannel?: string;
  slackNotifyBuildStart?: boolean;
  slackNotifyBuildComplete?: boolean;
  slackNotifyBuildFailed?: boolean;
  slackNotifySpecApproval?: boolean;
  updateEnvConfig: (updates: Partial<{
    slackEnabled: boolean;
    slackWebhookUrl: string;
    slackChannel: string;
    slackNotifyBuildStart: boolean;
    slackNotifyBuildComplete: boolean;
    slackNotifyBuildFailed: boolean;
    slackNotifySpecApproval: boolean;
  }>) => void;
}

/**
 * Slack integration settings component.
 * Manages Slack webhook URL, channel configuration, and notification preferences.
 */
export function SlackIntegration({
  slackEnabled,
  slackWebhookUrl,
  slackChannel,
  slackNotifyBuildStart = true,
  slackNotifyBuildComplete = true,
  slackNotifyBuildFailed = true,
  slackNotifySpecApproval = true,
  updateEnvConfig
}: SlackIntegrationProps) {
  const [connectionStatus, setConnectionStatus] = useState<SlackConnectionStatus | null>(null);
  const [isCheckingConnection, setIsCheckingConnection] = useState(false);

  debugLog('Render - slackEnabled:', slackEnabled);
  debugLog('Render - slackChannel:', slackChannel);
  debugLog('Render - hasWebhook:', !!slackWebhookUrl);

  // Check connection when webhook URL or channel changes
  useEffect(() => {
    if (slackEnabled && slackWebhookUrl) {
      debugLog('Webhook or channel changed, checking connection...');
      const timer = setTimeout(() => {
        checkConnection();
      }, 500);
      return () => clearTimeout(timer);
    } else {
      setConnectionStatus(null);
    }
  }, [slackEnabled, slackWebhookUrl, slackChannel]);

  const checkConnection = async () => {
    if (!slackWebhookUrl) {
      debugLog('checkConnection: No webhook URL, skipping');
      return;
    }

    debugLog('checkConnection: Starting validation...');
    setIsCheckingConnection(true);

    try {
      // Basic webhook URL validation
      const isValid = slackWebhookUrl.startsWith('https://hooks.slack.com/');

      if (isValid) {
        setConnectionStatus({
          connected: true,
          webhookValid: true,
          channelName: slackChannel || 'default'
        });
        debugLog('checkConnection: Webhook URL is valid');
      } else {
        setConnectionStatus({
          connected: false,
          webhookValid: false,
          error: 'Invalid webhook URL format'
        });
        debugLog('checkConnection: Invalid webhook URL format');
      }
    } catch (err) {
      debugLog('checkConnection: Exception:', err);
      setConnectionStatus({
        connected: false,
        error: err instanceof Error ? err.message : 'Connection check failed'
      });
    } finally {
      setIsCheckingConnection(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label className="font-normal text-foreground">Enable Slack Notifications</Label>
          <p className="text-xs text-muted-foreground">
            Receive build updates and spec approval requests in Slack
          </p>
        </div>
        <Switch
          checked={slackEnabled}
          onCheckedChange={(checked) => updateEnvConfig({ slackEnabled: checked })}
        />
      </div>

      {slackEnabled && (
        <>
          {/* Webhook URL Input */}
          <div className="space-y-2">
            <Label className="text-sm font-medium text-foreground">Webhook URL</Label>
            <p className="text-xs text-muted-foreground">
              Create a webhook from your Slack workspace settings
            </p>
            <Input
              type="url"
              placeholder="https://hooks.slack.com/services/T00/B00/XXX"
              value={slackWebhookUrl || ''}
              onChange={(e) => updateEnvConfig({ slackWebhookUrl: e.target.value })}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Navigate to{' '}
              <a
                href="https://api.slack.com/messaging/webhooks"
                target="_blank"
                rel="noopener noreferrer"
                className="text-info hover:underline"
              >
                Slack API docs
              </a>
              {' '}for setup instructions
            </p>
          </div>

          {/* Channel Input */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Hash className="h-4 w-4 text-muted-foreground" />
              <Label className="text-sm font-medium text-foreground">Channel</Label>
            </div>
            <p className="text-xs text-muted-foreground pl-6">
              Default channel for notifications (e.g., #builds, #dev-updates)
            </p>
            <div className="relative pl-6">
              <Input
                placeholder="#builds"
                value={slackChannel || ''}
                onChange={(e) => updateEnvConfig({ slackChannel: e.target.value })}
                className="text-sm"
              />
            </div>
          </div>

          {/* Connection Status */}
          {slackWebhookUrl && (
            <ConnectionStatus
              isChecking={isCheckingConnection}
              connectionStatus={connectionStatus}
            />
          )}

          <Separator />

          {/* Notification Preferences */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-muted-foreground" />
              <Label className="text-sm font-medium text-foreground">Notification Preferences</Label>
            </div>

            <div className="pl-6 space-y-4">
              <NotificationToggle
                icon={<Send className="h-4 w-4" />}
                label="Build Started"
                description="Notify when a new build begins"
                checked={slackNotifyBuildStart}
                onCheckedChange={(checked) => updateEnvConfig({ slackNotifyBuildStart: checked })}
              />

              <NotificationToggle
                icon={<CheckCircle2 className="h-4 w-4" />}
                label="Build Completed"
                description="Notify when a build finishes successfully"
                checked={slackNotifyBuildComplete}
                onCheckedChange={(checked) => updateEnvConfig({ slackNotifyBuildComplete: checked })}
              />

              <NotificationToggle
                icon={<AlertCircle className="h-4 w-4" />}
                label="Build Failed"
                description="Notify when a build fails"
                checked={slackNotifyBuildFailed}
                onCheckedChange={(checked) => updateEnvConfig({ slackNotifyBuildFailed: checked })}
              />

              <NotificationToggle
                icon={<MessageSquare className="h-4 w-4" />}
                label="Spec Approval Requests"
                description="Send approval requests to Slack for review"
                checked={slackNotifySpecApproval}
                onCheckedChange={(checked) => updateEnvConfig({ slackNotifySpecApproval: checked })}
              />
            </div>
          </div>

          <Separator />

          {/* Test Notification */}
          <div className="pl-6">
            <TestNotificationButton
              webhookUrl={slackWebhookUrl}
              channel={slackChannel}
              disabled={!slackWebhookUrl || !connectionStatus?.connected}
            />
          </div>
        </>
      )}
    </div>
  );
}

interface ConnectionStatusProps {
  isChecking: boolean;
  connectionStatus: SlackConnectionStatus | null;
}

function ConnectionStatus({ isChecking, connectionStatus }: ConnectionStatusProps) {
  return (
    <div className="rounded-lg border border-border bg-muted/30 p-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-foreground">Connection Status</p>
          <p className="text-xs text-muted-foreground">
            {isChecking ? 'Checking...' :
              connectionStatus?.connected
                ? `Configured for ${connectionStatus.channelName || 'default channel'}`
                : connectionStatus?.error || 'Not configured'}
          </p>
        </div>
        {isChecking ? (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        ) : connectionStatus?.connected ? (
          <CheckCircle2 className="h-4 w-4 text-success" />
        ) : (
          <AlertCircle className="h-4 w-4 text-warning" />
        )}
      </div>
    </div>
  );
}

interface NotificationToggleProps {
  icon: React.ReactNode;
  label: string;
  description: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}

function NotificationToggle({ icon, label, description, checked, onCheckedChange }: NotificationToggleProps) {
  return (
    <div className="flex items-center justify-between">
      <div className="space-y-0.5">
        <div className="flex items-center gap-2">
          {icon}
          <Label className="font-normal text-foreground text-sm">{label}</Label>
        </div>
        <p className="text-xs text-muted-foreground pl-6">{description}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  );
}

interface TestNotificationButtonProps {
  webhookUrl?: string;
  channel?: string;
  disabled: boolean;
}

function TestNotificationButton({ webhookUrl, channel, disabled }: TestNotificationButtonProps) {
  const [isSending, setIsSending] = useState(false);
  const [sendResult, setSendResult] = useState<'success' | 'error' | null>(null);

  const handleSendTest = async () => {
    if (!webhookUrl) return;

    setIsSending(true);
    setSendResult(null);

    try {
      const response = await fetch(webhookUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: '✅ Auto Claude Slack integration test successful!',
          channel: channel || undefined,
        }),
      });

      if (response.ok) {
        setSendResult('success');
        setTimeout(() => setSendResult(null), 3000);
      } else {
        setSendResult('error');
      }
    } catch (err) {
      setSendResult('error');
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={handleSendTest}
        disabled={disabled || isSending}
        className="gap-2"
      >
        {isSending ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : sendResult === 'success' ? (
          <CheckCircle2 className="h-3 w-3 text-success" />
        ) : sendResult === 'error' ? (
          <AlertCircle className="h-3 w-3 text-destructive" />
        ) : (
          <Send className="h-3 w-3" />
        )}
        {isSending ? 'Sending...' : sendResult === 'success' ? 'Sent!' : 'Send Test Notification'}
      </Button>
      <p className="text-xs text-muted-foreground">
        Send a test message to verify your webhook is working
      </p>
    </div>
  );
}
