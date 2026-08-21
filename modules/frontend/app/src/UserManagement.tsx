import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, RefreshCw, ScrollText, UserPlus } from "lucide-react";
import { authFetch, getErrorMessage } from "./auth";

interface Props {
  onBack: () => void;
  onUnauthorized: () => void;
}

interface UserRecord {
  id: string | number;
  account: string;
  role: string;
  department: string;
  isActive: boolean;
}

interface AuditLogRecord {
  logId: string | number;
  time: string;
  account: string;
  action: string;
  details: string;
}

const normalizeUser = (value: unknown, index: number): UserRecord | null => {
  if (!value || typeof value !== "object") return null;
  const user = value as Record<string, unknown>;
  const id = user.id ?? user.user_id ?? `user-${index}`;

  return {
    id: typeof id === "string" || typeof id === "number" ? id : `user-${index}`,
    account: typeof user.account === "string" ? user.account : "未提供",
    role: typeof user.role === "string" ? user.role : "一般人員",
    department: typeof user.department === "string" ? user.department : "未提供",
    isActive: typeof user.is_active === "boolean" ? user.is_active : true,
  };
};

const normalizeAuditLog = (
  value: unknown,
  index: number
): AuditLogRecord | null => {
  if (!value || typeof value !== "object") return null;
  const log = value as Record<string, unknown>;
  const logId = log.log_id ?? `log-${index}`;

  return {
    logId: typeof logId === "string" || typeof logId === "number"
      ? logId
      : `log-${index}`,
    time: typeof log.time === "string" ? log.time : "未提供",
    account: typeof log.account === "string" ? log.account : "未知帳號",
    action: typeof log.action === "string" ? log.action : "未提供",
    details: typeof log.details === "string" && log.details.trim()
      ? log.details
      : "無",
  };
};

export default function UserManagement({ onBack, onUnauthorized }: Props) {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [account, setAccount] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("一般人員");
  const [department, setDepartment] = useState("");
  const [saving, setSaving] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [logsLoading, setLogsLoading] = useState(true);
  const [logsError, setLogsError] = useState<string | null>(null);

  const handleResponseError = useCallback(async (response: Response) => {
    if (response.status === 401) {
      onUnauthorized();
      throw new Error("登入已失效，請重新登入");
    }

    if (response.status === 403) {
      throw new Error(await getErrorMessage(response));
    }

    throw new Error(await getErrorMessage(response));
  }, [onUnauthorized]);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const response = await authFetch("/api/users/");
      if (!response.ok) await handleResponseError(response);

      const payload = (await response.json()) as unknown;
      const list = Array.isArray(payload)
        ? payload
        : payload && typeof payload === "object" && Array.isArray((payload as { data?: unknown }).data)
          ? (payload as { data: unknown[] }).data
          : payload && typeof payload === "object" && Array.isArray((payload as { users?: unknown }).users)
            ? (payload as { users: unknown[] }).users
            : [];
      setUsers(list.map(normalizeUser).filter((user): user is UserRecord => user !== null));
      setError(null);
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "未知錯誤";
      console.error("[USER_LIST_FETCH_FAILED]", { message, time: new Date().toISOString() });
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [handleResponseError]);

  const loadAuditLogs = useCallback(async () => {
    setLogsLoading(true);
    try {
      const response = await authFetch("/api/users/audit-logs");
      if (!response.ok) await handleResponseError(response);

      const payload = (await response.json()) as unknown;
      const list = Array.isArray(payload)
        ? payload
        : payload && typeof payload === "object" && Array.isArray((payload as { data?: unknown }).data)
          ? (payload as { data: unknown[] }).data
          : payload && typeof payload === "object" && Array.isArray((payload as { logs?: unknown }).logs)
            ? (payload as { logs: unknown[] }).logs
            : [];

      setAuditLogs(
        list
          .map(normalizeAuditLog)
          .filter((log): log is AuditLogRecord => log !== null)
      );
      setLogsError(null);
    } catch (requestError) {
      const message = requestError instanceof Error
        ? requestError.message
        : "未知錯誤";
      console.error("[AUDIT_LOGS_FETCH_FAILED]", {
        message,
        time: new Date().toISOString(),
      });
      setLogsError(message);
    } finally {
      setLogsLoading(false);
    }
  }, [handleResponseError]);

  useEffect(() => {
    loadUsers();
    loadAuditLogs();
  }, [loadAuditLogs, loadUsers]);

  const createUser = async (event: FormEvent) => {
    event.preventDefault();
    if (!account.trim() || !password || !department.trim()) return;
    setSaving(true);
    try {
      const response = await authFetch("/api/users/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          account: account.trim(),
          password,
          role,
          department: department.trim(),
        }),
      });
      if (!response.ok) await handleResponseError(response);
      setAccount("");
      setPassword("");
      setDepartment("");
      await Promise.all([loadUsers(), loadAuditLogs()]);
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "未知錯誤";
      alert(`新增失敗：${message}`);
    } finally {
      setSaving(false);
    }
  };

  const updateRole = async (userId: UserRecord["id"], newRole: string) => {
    try {
      const response = await authFetch(`/api/users/${userId}/role`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: newRole }),
      });
      if (!response.ok) await handleResponseError(response);
      await Promise.all([loadUsers(), loadAuditLogs()]);
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "未知錯誤";
      alert(`修改失敗：${message}`);
    }
  };

  const toggleStatus = async (userId: UserRecord["id"]) => {
    try {
      const response = await authFetch(`/api/users/${userId}/toggle-status`, { method: "PUT" });
      if (!response.ok) await handleResponseError(response);
      await Promise.all([loadUsers(), loadAuditLogs()]);
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "未知錯誤";
      alert(`狀態變更失敗：${message}`);
    }
  };

  const deleteUser = async (user: UserRecord) => {
    if (!confirm(`確定要刪除帳號「${user.account}」嗎？此動作無法復原。`)) return;
    try {
      const response = await authFetch(`/api/users/${user.id}`, { method: "DELETE" });
      if (!response.ok) await handleResponseError(response);
      await Promise.all([loadUsers(), loadAuditLogs()]);
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "未知錯誤";
      alert(`無法刪除：${message}`);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#2B4C7E] to-[#1A2F4F] p-6">
      <div className="max-w-6xl mx-auto bg-white rounded-3xl p-8 shadow-2xl">
        <button type="button" onClick={onBack} className="flex items-center gap-2 text-gray-500 hover:text-blue-600 mb-5">
          <ArrowLeft size={19} />返回主頁
        </button>
        <h1 className="text-2xl font-bold text-gray-800">人員與權限管理</h1>
        <p className="text-sm text-gray-500 mt-1 mb-7">新增帳號、調整權限及管理使用狀態。</p>

        <form onSubmit={createUser} className="grid grid-cols-1 md:grid-cols-5 gap-3 bg-blue-50 border border-blue-100 rounded-xl p-4 mb-8">
          <input value={account} onChange={(event) => setAccount(event.target.value)} placeholder="帳號" className="border rounded-lg px-3 py-2.5" />
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="密碼" className="border rounded-lg px-3 py-2.5" />
          <select value={role} onChange={(event) => setRole(event.target.value)} className="border rounded-lg px-3 py-2.5 bg-white">
            <option>一般人員</option><option>系統管理員</option>
          </select>
          <input value={department} onChange={(event) => setDepartment(event.target.value)} placeholder="部門" className="border rounded-lg px-3 py-2.5" />
          <button disabled={saving} className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded-lg px-4 py-2.5 flex items-center justify-center gap-2">
            <UserPlus size={18} />{saving ? "儲存中…" : "新增人員"}
          </button>
        </form>

        {error && <div className="mb-5 bg-red-50 border border-red-200 text-red-700 rounded-lg p-3">{error}</div>}

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-gray-600">
              <tr><th className="p-3 text-left">帳號</th><th className="p-3 text-left">部門</th><th className="p-3 text-left">權限</th><th className="p-3 text-left">狀態</th><th className="p-3 text-right">操作</th></tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className={`border-b ${user.isActive ? "bg-white" : "bg-gray-100 text-gray-400"}`}>
                  <td className="p-3 font-medium">{user.account}</td>
                  <td className="p-3">{user.department}</td>
                  <td className="p-3">
                    <select value={user.role} onChange={(event) => updateRole(user.id, event.target.value)} className="border rounded px-2 py-1.5 bg-white text-gray-700">
                      <option>一般人員</option><option>系統管理員</option>
                    </select>
                  </td>
                  <td className="p-3">
                    <button type="button" onClick={() => toggleStatus(user.id)} className={`px-3 py-1.5 rounded-full text-white ${user.isActive ? "bg-green-500" : "bg-red-500"}`}>
                      {user.isActive ? "正常（點擊凍結）" : "已停用（點擊解凍）"}
                    </button>
                  </td>
                  <td className="p-3 text-right"><button type="button" onClick={() => deleteUser(user)} className="text-red-500 hover:text-red-700">刪除</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {loading && <div className="text-center text-gray-400 py-10">正在取得人員名單…</div>}
          {!loading && users.length === 0 && <div className="text-center text-gray-400 py-10">目前沒有人員資料</div>}
        </div>

        <section className="mt-10 border-t border-gray-200 pt-8">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="flex items-center gap-2 text-xl font-bold text-gray-800">
                <ScrollText size={21} className="text-[#2B4C7E]" />
                操作日誌
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                追蹤系統人員的操作紀錄與詳細內容。
              </p>
            </div>
            <button
              type="button"
              onClick={loadAuditLogs}
              disabled={logsLoading}
              className="flex items-center gap-2 rounded-lg bg-[#2B4C7E] px-4 py-2 text-sm font-medium text-white hover:bg-[#1A2F4F] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw size={16} className={logsLoading ? "animate-spin" : ""} />
              刷新日誌
            </button>
          </div>

          {logsError && (
            <div className="mb-5 rounded-lg border border-red-200 bg-red-50 p-3 text-red-700">
              無法取得操作日誌：{logsError}
            </div>
          )}

          <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="w-full min-w-[820px] text-sm">
              <thead className="bg-gray-100 text-gray-600">
                <tr>
                  <th className="p-3 text-left">紀錄編號</th>
                  <th className="p-3 text-left">發生時間</th>
                  <th className="p-3 text-left">操作人員</th>
                  <th className="p-3 text-left">執行動作</th>
                  <th className="p-3 text-left">詳細說明</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((log) => (
                  <tr key={log.logId} className="border-t border-gray-100 bg-white align-top hover:bg-blue-50/40">
                    <td className="p-3 font-medium text-gray-700">{log.logId}</td>
                    <td className="whitespace-nowrap p-3 text-gray-600">{log.time}</td>
                    <td className="p-3">
                      <span className="inline-flex rounded-full bg-blue-100 px-3 py-1 font-medium text-blue-700">
                        {log.account}
                      </span>
                    </td>
                    <td className="p-3 font-medium text-gray-700">{log.action}</td>
                    <td className="p-3 text-gray-600">{log.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {logsLoading && (
              <div className="py-10 text-center text-gray-400">正在取得操作日誌…</div>
            )}
            {!logsLoading && !logsError && auditLogs.length === 0 && (
              <div className="py-10 text-center text-gray-400">目前沒有操作日誌</div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
