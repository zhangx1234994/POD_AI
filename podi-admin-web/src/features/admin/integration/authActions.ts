import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { adminApi } from '../../../services/adminApi';
import type {
  AuthScopeSummaryResponse,
  AuthSession,
  AuthUser,
  AuthUserFormState,
  AuthUserUpdatePayload,
  InviteCode,
  InviteCodeCreatePayload,
} from '../../../types/admin';
import { defaultInviteCodeForm } from './integrationDashboardConfig';

interface AuthActionsParams {
  authInviteForm: InviteCodeCreatePayload;
  authUserForm: AuthUserFormState;
  extractErrorMessage: (error: unknown) => string;
  setAuthError: Dispatch<SetStateAction<string | null>>;
  setAuthInviteForm: Dispatch<SetStateAction<InviteCodeCreatePayload>>;
  setAuthLoading: Dispatch<SetStateAction<boolean>>;
  setAuthScopeSummary: Dispatch<SetStateAction<AuthScopeSummaryResponse | null>>;
  setAuthSessions: Dispatch<SetStateAction<AuthSession[]>>;
  setAuthUserForm: Dispatch<SetStateAction<AuthUserFormState>>;
  setAuthUsers: Dispatch<SetStateAction<AuthUser[]>>;
  setInviteCodes: Dispatch<SetStateAction<InviteCode[]>>;
}

export const useAuthActions = ({
  authInviteForm,
  authUserForm,
  extractErrorMessage,
  setAuthError,
  setAuthInviteForm,
  setAuthLoading,
  setAuthScopeSummary,
  setAuthSessions,
  setAuthUserForm,
  setAuthUsers,
  setInviteCodes,
}: AuthActionsParams) => {
  const refreshAuthPanel = useCallback(async () => {
    setAuthLoading(true);
    setAuthError(null);
    try {
      const [users, sessions, invites, scopeSummary] = await Promise.all([
        adminApi.listAuthUsers(),
        adminApi.listAuthSessions(),
        adminApi.listInviteCodes(),
        adminApi.getAuthScopeSummary(),
      ]);
      setAuthUsers(users.items || []);
      setAuthSessions(sessions.items || []);
      setInviteCodes(invites.items || []);
      setAuthScopeSummary(scopeSummary);
    } catch (error) {
      setAuthError(extractErrorMessage(error) || '账号权限数据加载失败');
    } finally {
      setAuthLoading(false);
    }
  }, [
    extractErrorMessage,
    setAuthError,
    setAuthLoading,
    setAuthScopeSummary,
    setAuthSessions,
    setAuthUsers,
    setInviteCodes,
  ]);

  const handleAuthInviteSubmit = useCallback(async () => {
    setAuthError(null);
    try {
      const payload: InviteCodeCreatePayload = {
        role: authInviteForm.role || 'user',
        tenantId: authInviteForm.tenantId?.trim() || undefined,
        clientId: authInviteForm.clientId?.trim() || undefined,
        maxUses: Math.max(1, Number(authInviteForm.maxUses || 1)),
        expiresAt: authInviteForm.expiresAt || undefined,
        note: authInviteForm.note?.trim() || undefined,
        metadata: authInviteForm.metadata,
      };
      await adminApi.createInviteCode(payload);
      setAuthInviteForm(defaultInviteCodeForm);
      await refreshAuthPanel();
    } catch (error) {
      setAuthError(extractErrorMessage(error) || '邀请码生成失败');
    }
  }, [
    authInviteForm,
    extractErrorMessage,
    refreshAuthPanel,
    setAuthError,
    setAuthInviteForm,
  ]);

  const handleAuthUserEditSelect = useCallback(
    (user: AuthUser) => {
      setAuthUserForm({
        userId: user.id,
        displayName: user.displayName || '',
        role: user.role || 'user',
        status: user.status || 'active',
        tenantId: user.tenantId || '',
        clientId: user.clientId || '',
        note: '',
      });
    },
    [setAuthUserForm],
  );

  const handleAuthUserSubmit = useCallback(async () => {
    const userId = authUserForm.userId?.trim();
    if (!userId) {
      setAuthError('请先选择要调整的账号。');
      return;
    }
    setAuthError(null);
    setAuthLoading(true);
    try {
      const payload: AuthUserUpdatePayload = {
        displayName: authUserForm.displayName?.trim() || null,
        role: authUserForm.role || 'user',
        status: authUserForm.status || 'active',
        tenantId: authUserForm.tenantId?.trim() || null,
        clientId: authUserForm.clientId?.trim() || null,
        note: authUserForm.note?.trim() || undefined,
      };
      const updated = await adminApi.updateAuthUser(userId, payload);
      setAuthUserForm({
        userId: updated.id,
        displayName: updated.displayName || '',
        role: updated.role || 'user',
        status: updated.status || 'active',
        tenantId: updated.tenantId || '',
        clientId: updated.clientId || '',
        note: '',
      });
      await refreshAuthPanel();
    } catch (error) {
      setAuthError(extractErrorMessage(error) || '账号调整失败');
    } finally {
      setAuthLoading(false);
    }
  }, [
    authUserForm,
    extractErrorMessage,
    refreshAuthPanel,
    setAuthError,
    setAuthLoading,
    setAuthUserForm,
  ]);

  const handleAuthInviteDisable = useCallback(
    async (invite: InviteCode) => {
      if (!window.confirm(`确认让邀请码 ${invite.code} 立即失效？`)) return;
      setAuthError(null);
      setAuthLoading(true);
      try {
        await adminApi.disableInviteCode(invite.id);
        await refreshAuthPanel();
      } catch (error) {
        setAuthError(extractErrorMessage(error) || '邀请码失效失败');
      } finally {
        setAuthLoading(false);
      }
    },
    [extractErrorMessage, refreshAuthPanel, setAuthError, setAuthLoading],
  );

  const handleAuthSessionRevoke = useCallback(
    async (session: AuthSession) => {
      const label = session.displayName || session.username || session.email || session.id;
      if (!window.confirm(`确认踢出 ${label} 的这个登录会话？`)) return;
      setAuthError(null);
      setAuthLoading(true);
      try {
        await adminApi.revokeAuthSession(session.id);
        await refreshAuthPanel();
      } catch (error) {
        setAuthError(extractErrorMessage(error) || '会话踢出失败');
      } finally {
        setAuthLoading(false);
      }
    },
    [extractErrorMessage, refreshAuthPanel, setAuthError, setAuthLoading],
  );

  return {
    handleAuthInviteDisable,
    handleAuthInviteSubmit,
    handleAuthSessionRevoke,
    handleAuthUserEditSelect,
    handleAuthUserSubmit,
    refreshAuthPanel,
  };
};
