import { useState } from "react";
import { ArrowLeft } from "lucide-react";

interface Props {
  onBack: () => void;
}

export default function WebsiteQuery({ onBack }: Props) {
  const [tab, setTab] = useState<"list" | "black" | "white">("list");
  const [search, setSearch] = useState("");

  // 假資料
  const data = [
    { id: 1, name: "dark-market-x.onion", location: "Unknown", score: 95 },
    { id: 2, name: "buy-weed-online.com", location: "Netherlands", score: 88 },
    { id: 3, name: "chem-supply-ltd.net", location: "Russia", score: 92 },
    { id: 4, name: "google.com", location: "USA", score: 10 },
  ];

  // 黑名單
  const [blacklist, setBlacklist] = useState<string[]>([
    "dark-market-x.onion",
  ]);

  // 白名單
  const [whitelist, setWhitelist] = useState<string[]>([
    "google.com",
  ]);

  const [input, setInput] = useState("");

  const addItem = (type: "black" | "white") => {
    if (!input) return;

    if (type === "black") {
      setBlacklist([...blacklist, input]);
    } else {
      setWhitelist([...whitelist, input]);
    }

    setInput("");
  };

  const removeItem = (type: "black" | "white", index: number) => {
    if (type === "black") {
      const newList = [...blacklist];
      newList.splice(index, 1);
      setBlacklist(newList);
    } else {
      const newList = [...whitelist];
      newList.splice(index, 1);
      setWhitelist(newList);
    }
  };

  // ⭐ 風險判斷（重點🔥）
  const getFinalScore = (item: any) => {
    if (whitelist.includes(item.name)) return 10;
    if (blacklist.includes(item.name)) return 95;
    return item.score;
  };

  const getColor = (score: number) => {
    if (score >= 85) return "bg-red-500";
    if (score >= 60) return "bg-yellow-400";
    return "bg-green-500";
  };

  const getStatus = (name: string) => {
    if (whitelist.includes(name)) return "白名單";
    if (blacklist.includes(name)) return "黑名單";
    return "一般";
  };

  const filtered = data.filter((item) =>
    item.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#2B4C7E] to-[#1a2f4f] p-6">
      <div className="max-w-6xl mx-auto bg-white rounded-2xl shadow-xl p-8">

        {/* 返回 */}
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-gray-500 hover:text-blue-500 mb-6"
        >
          <ArrowLeft className="w-5 h-5" />
          返回主頁
        </button>

        <h1 className="text-2xl font-bold mb-6">網站資料庫</h1>

        {/* Tabs */}
        <div className="flex gap-3 mb-6">
          <button onClick={() => setTab("list")} className={`px-4 py-2 rounded ${tab==="list"?"bg-blue-500 text-white":"bg-gray-100"}`}>
            網站列表
          </button>
          <button onClick={() => setTab("black")} className={`px-4 py-2 rounded ${tab==="black"?"bg-red-500 text-white":"bg-gray-100"}`}>
            黑名單
          </button>
          <button onClick={() => setTab("white")} className={`px-4 py-2 rounded ${tab==="white"?"bg-green-500 text-white":"bg-gray-100"}`}>
            白名單
          </button>
        </div>

        {/* ====== 網站列表 ====== */}
        {tab === "list" && (
          <>
            <input
              placeholder="搜尋網站..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full border px-4 py-2 rounded mb-6"
            />

            <table className="w-full text-sm border">
              <thead className="bg-gray-100">
                <tr>
                  <th className="p-2">網站</th>
                  <th>位置</th>
                  <th>風險</th>
                  <th>狀態</th>
                </tr>
              </thead>

              <tbody>
                {filtered.map((item) => {
                  const score = getFinalScore(item);

                  return (
                    <tr key={item.id} className="border-t text-center">
                      <td className="p-2 text-blue-600">{item.name}</td>
                      <td>{item.location}</td>

                      {/* 風險條 */}
                      <td>
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-20 h-2 bg-gray-200 rounded">
                            <div
                              className={`h-2 rounded ${getColor(score)}`}
                              style={{ width: `${score}%` }}
                            />
                          </div>
                          {score}
                        </div>
                      </td>

                      {/* 狀態 */}
                      <td>
                        <span
                          className={`px-2 py-1 text-xs rounded ${
                            whitelist.includes(item.name)
                              ? "bg-green-100 text-green-600"
                              : blacklist.includes(item.name)
                              ? "bg-red-100 text-red-500"
                              : "bg-gray-100"
                          }`}
                        >
                          {getStatus(item.name)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}

        {/* ====== 黑名單 ====== */}
        {tab === "black" && (
          <>
            <div className="flex gap-2 mb-4">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                className="border px-3 py-2 flex-1"
                placeholder="新增黑名單..."
              />
              <button onClick={() => addItem("black")} className="bg-red-500 text-white px-4 rounded">
                新增
              </button>
            </div>

            {blacklist.map((item, i) => (
              <div key={i} className="flex justify-between border p-2 mb-2">
                {item}
                <button onClick={() => removeItem("black", i)} className="text-red-500">
                  刪除
                </button>
              </div>
            ))}
          </>
        )}

        {/* ====== 白名單 ====== */}
        {tab === "white" && (
          <>
            <div className="flex gap-2 mb-4">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                className="border px-3 py-2 flex-1"
                placeholder="新增白名單..."
              />
              <button onClick={() => addItem("white")} className="bg-green-500 text-white px-4 rounded">
                新增
              </button>
            </div>

            {whitelist.map((item, i) => (
              <div key={i} className="flex justify-between border p-2 mb-2">
                {item}
                <button onClick={() => removeItem("white", i)} className="text-green-600">
                  刪除
                </button>
              </div>
            ))}
          </>
        )}

      </div>
    </div>
  );
}