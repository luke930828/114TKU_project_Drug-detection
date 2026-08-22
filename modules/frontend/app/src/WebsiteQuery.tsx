import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Check, ShieldAlert, ShieldCheck } from "lucide-react";
import { authFetch, getErrorMessage } from "./auth";
import { hasMaliciousInput, MALICIOUS_INPUT_MESSAGE } from "./inputSecurity";

export interface PendingWebsite {
  url: string;
  score: number;
  riskLevel: string;
  detectedAt: string;
}

interface WhitelistEntry {
  id: string | number;
  url: string;
  title: string;
  reason: string;
}

const normalizeWhitelistEntry = (
  value: unknown,
  index: number
): WhitelistEntry | null => {
  if (!value || typeof value !== "object") return null;
  const entry = value as Record<string, unknown>;
  const id = entry.id ?? entry.whitelist_id ?? `whitelist-${index}`;
  if (typeof entry.url !== "string" || !entry.url.trim()) return null;

  return {
    id: typeof id === "string" || typeof id === "number"
      ? id
      : `whitelist-${index}`,
    url: entry.url,
    title: typeof entry.title === "string" ? entry.title : "未提供",
    reason: typeof entry.reason === "string" && entry.reason.trim()
      ? entry.reason
      : "無",
  };
};

interface Props {
  onBack: () => void;
  blacklist: string[];
  pendingSites: PendingWebsite[];
  onAdd: (type: "black" | "white", url: string) => void;
  onRemove: (type: "black" | "white", url: string) => void;
  onClassify: (url: string, type: "black" | "white") => void;
}

export default function WebsiteQuery({
  onBack,
  blacklist,
  pendingSites,
  onAdd,
  onRemove,
  onClassify,
}: Props) {
  const [tab, setTab] = useState<"black" | "white" | "pending">("pending");
  const [input, setInput] = useState("");
  const [whiteUrl, setWhiteUrl] = useState("");
  const [whiteTitle, setWhiteTitle] = useState("");
  const [whiteReason, setWhiteReason] = useState("");
  const [whitelistEntries, setWhitelistEntries] = useState<WhitelistEntry[]>([]);
  const [whitelistLoading, setWhitelistLoading] = useState(true);
  const [whitelistError, setWhitelistError] = useState<string | null>(null);
  const [whitelistSaving, setWhitelistSaving] = useState(false);

  const addBlacklistItem = () => {
    const value = input.trim();
    if (!value) return;
    if (hasMaliciousInput([value])) {
      alert(MALICIOUS_INPUT_MESSAGE);
      return;
    }
    onAdd("black", value);
    setInput("");
  };

  const loadWhitelist = useCallback(async () => {
    setWhitelistLoading(true);
    try {
      const response = await authFetch("/api/whitelist/");
      if (!response.ok) throw new Error(await getErrorMessage(response));

      const payload = (await response.json()) as unknown;
      const list = Array.isArray(payload)
        ? payload
        : payload && typeof payload === "object" && Array.isArray((payload as { data?: unknown }).data)
          ? (payload as { data: unknown[] }).data
          : payload && typeof payload === "object" && Array.isArray((payload as { whitelist?: unknown }).whitelist)
            ? (payload as { whitelist: unknown[] }).whitelist
            : [];
      setWhitelistEntries(
        list
          .map(normalizeWhitelistEntry)
          .filter((entry): entry is WhitelistEntry => entry !== null)
      );
      setWhitelistError(null);
    } catch (requestError) {
      const message = requestError instanceof Error
        ? requestError.message
        : "未知錯誤";
      setWhitelistError(message);
      console.error("[WHITELIST_FETCH_FAILED]", {
        message,
        time: new Date().toISOString(),
      });
    } finally {
      setWhitelistLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWhitelist();
  }, [loadWhitelist]);

  const addWhitelistEntry = async () => {
    const url = whiteUrl.trim();
    const title = whiteTitle.trim();
    const reason = whiteReason.trim();
    if (!url || !title || !reason) {
      alert("請完整填寫網址、標題與加入原因。");
      return;
    }
    if (hasMaliciousInput([url, title, reason])) {
      alert(MALICIOUS_INPUT_MESSAGE);
      return;
    }

    setWhitelistSaving(true);
    try {
      const response = await authFetch("/api/whitelist/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, title, reason }),
      });
      if (!response.ok) throw new Error(await getErrorMessage(response));

      const result = (await response.json()) as { message?: string };
      onAdd("white", url);
      setWhiteUrl("");
      setWhiteTitle("");
      setWhiteReason("");
      await loadWhitelist();
      alert(result.message || "白名單新增成功！");
    } catch (requestError) {
      const message = requestError instanceof Error
        ? requestError.message
        : "未知錯誤";
      alert(`白名單新增失敗：${message}`);
    } finally {
      setWhitelistSaving(false);
    }
  };

  const deleteWhitelistEntry = async (entry: WhitelistEntry) => {
    if (!confirm("確定要刪除這筆白名單嗎？刪除後該網址將重新接受爬蟲與 AI 檢測。")) {
      return;
    }

    try {
      const response = await authFetch(`/api/whitelist/${entry.id}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error(await getErrorMessage(response));

      onRemove("white", entry.url);
      await loadWhitelist();
      alert("白名單刪除成功！");
    } catch (requestError) {
      const message = requestError instanceof Error
        ? requestError.message
        : "未知錯誤";
      alert(`白名單刪除失敗：${message}`);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#2B4C7E] to-[#1a2f4f] p-6">
      <div className="max-w-6xl mx-auto bg-white rounded-2xl shadow-xl p-8">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-2 text-gray-500 hover:text-blue-500 mb-6"
        >
          <ArrowLeft className="w-5 h-5" />
          返回主頁
        </button>

        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <div>
            <h1 className="text-2xl font-bold">網站名單管理</h1>
            <p className="text-sm text-gray-500 mt-1">
              AI 判定為可疑的網站，需由警員確認後才能正式分類。
            </p>
          </div>
          {pendingSites.length > 0 && (
            <span className="bg-amber-100 text-amber-700 px-3 py-1.5 rounded-full text-sm font-medium">
              {pendingSites.length} 筆待確認
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-3 mb-6 border-b pb-4">
          <button
            type="button"
            onClick={() => setTab("black")}
            className={`px-4 py-2 rounded-lg transition ${
              tab === "black" ? "bg-red-500 text-white" : "bg-gray-100 hover:bg-gray-200"
            }`}
          >
            黑名單（{blacklist.length}）
          </button>
          <button
            type="button"
            onClick={() => setTab("white")}
            className={`px-4 py-2 rounded-lg transition ${
              tab === "white" ? "bg-green-500 text-white" : "bg-gray-100 hover:bg-gray-200"
            }`}
          >
            白名單（{whitelistEntries.length}）
          </button>
          <button
            type="button"
            onClick={() => setTab("pending")}
            className={`px-4 py-2 rounded-lg transition ${
              tab === "pending" ? "bg-amber-500 text-white" : "bg-gray-100 hover:bg-gray-200"
            }`}
          >
            待確認（{pendingSites.length}）
          </button>
        </div>

        {tab === "black" && (
          <>
            <div className="flex flex-col sm:flex-row gap-2 mb-5">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") addBlacklistItem();
                }}
                className="border px-3 py-2.5 flex-1 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-200"
                placeholder="新增黑名單網址..."
              />
              <button
                type="button"
                onClick={addBlacklistItem}
                className="bg-red-500 hover:bg-red-600 text-white px-5 py-2.5 rounded-lg"
              >
                新增
              </button>
            </div>

            <div className="space-y-3">
              {blacklist.length === 0 ? (
                <div className="text-center text-gray-400 py-12 border-2 border-dashed rounded-xl">
                  目前沒有資料
                </div>
              ) : (
                blacklist.map((item) => (
                  <div key={item} className="flex items-center justify-between gap-3 border p-4 rounded-xl">
                    <div className="flex items-center gap-3 min-w-0">
                      <ShieldAlert className="text-red-500 shrink-0" />
                      <span className="break-all">{item}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => onRemove("black", item)}
                      className="text-gray-500 hover:text-red-500 shrink-0"
                    >
                      刪除
                    </button>
                  </div>
                ))
              )}
            </div>
          </>
        )}

        {tab === "white" && (
          <>
            <div className="mb-6 rounded-xl border border-green-200 bg-green-50/50 p-4">
              <h2 className="mb-3 font-bold text-gray-800">新增白名單</h2>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <input
                  value={whiteUrl}
                  onChange={(event) => setWhiteUrl(event.target.value)}
                  placeholder="網址"
                  className="rounded-lg border px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-green-200"
                />
                <input
                  value={whiteTitle}
                  onChange={(event) => setWhiteTitle(event.target.value)}
                  placeholder="標題"
                  className="rounded-lg border px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-green-200"
                />
                <input
                  value={whiteReason}
                  onChange={(event) => setWhiteReason(event.target.value)}
                  placeholder="加入原因"
                  className="rounded-lg border px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-green-200"
                />
              </div>
              <button
                type="button"
                onClick={addWhitelistEntry}
                disabled={whitelistSaving}
                className="mt-3 rounded-lg bg-green-500 px-5 py-2.5 text-white hover:bg-green-600 disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                {whitelistSaving ? "新增中…" : "新增白名單"}
              </button>
              <p className="mt-2 text-xs text-gray-500">此操作僅限最高管理員。</p>
            </div>

            {whitelistError && (
              <div className="mb-5 rounded-lg border border-red-200 bg-red-50 p-3 text-red-700">
                無法取得白名單：{whitelistError}
              </div>
            )}

            <div className="space-y-3">
              {whitelistLoading ? (
                <div className="py-12 text-center text-gray-400">正在取得白名單…</div>
              ) : whitelistEntries.length === 0 ? (
                <div className="text-center text-gray-400 py-12 border-2 border-dashed rounded-xl">
                  目前沒有白名單資料
                </div>
              ) : (
                whitelistEntries.map((entry) => (
                  <div key={entry.id} className="flex flex-col justify-between gap-3 rounded-xl border p-4 sm:flex-row sm:items-center">
                    <div className="flex min-w-0 items-start gap-3">
                      <ShieldCheck className="mt-0.5 shrink-0 text-green-500" />
                      <div className="min-w-0">
                        <p className="font-medium text-gray-800">{entry.title}</p>
                        <p className="mt-1 break-all text-blue-600">{entry.url}</p>
                        <p className="mt-1 text-sm text-gray-500">原因：{entry.reason}</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => deleteWhitelistEntry(entry)}
                      className="shrink-0 text-gray-500 hover:text-red-500"
                    >
                      刪除
                    </button>
                  </div>
                ))
              )}
            </div>
          </>
        )}

        {tab === "pending" && (
          <div className="space-y-4">
            {pendingSites.length === 0 ? (
              <div className="text-center py-14 border-2 border-dashed border-gray-200 rounded-xl">
                <Check className="w-10 h-10 text-green-500 mx-auto mb-3" />
                <p className="font-medium text-gray-700">目前沒有待確認網站</p>
                <p className="text-sm text-gray-400 mt-1">AI 發現可疑網站後會自動出現在這裡。</p>
              </div>
            ) : (
              pendingSites.map((site) => (
                <div key={site.url} className="border border-amber-200 bg-amber-50/50 rounded-xl p-5">
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-2">
                        <span className="bg-amber-500 text-white px-2.5 py-1 rounded-full text-xs font-medium">待確認</span>
                        <span className="text-red-600 font-bold">風險分數 {site.score}</span>
                        <span className="text-sm text-gray-500">{site.riskLevel}</span>
                      </div>
                      <p className="font-medium text-gray-800 break-all">{site.url}</p>
                      <p className="text-xs text-gray-400 mt-2">辨識時間：{site.detectedAt}</p>
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => onClassify(site.url, "black")}
                        className="bg-red-500 hover:bg-red-600 text-white px-4 py-2.5 rounded-lg"
                      >
                        加入黑名單
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setWhiteUrl(site.url);
                          setWhiteTitle("");
                          setWhiteReason("經警員人工確認");
                          setTab("white");
                        }}
                        className="bg-green-500 hover:bg-green-600 text-white px-4 py-2.5 rounded-lg"
                      >
                        加入白名單
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
