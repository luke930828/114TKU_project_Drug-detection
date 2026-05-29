import { useState } from "react";
import { ArrowLeft } from "lucide-react";

interface Props {
  onBack: () => void;
}

interface ResultType {
  id: number;
  time: string;
  content: string;
  drugType: string;
  language: string;
  riskLevel: "high" | "medium" | "low";
  score: number;
  caseNumber: string;
  detectedKeywords: string[];
  aiAnalysis: {
    type: string;
    description: string;
    confidence: number;
  }[];
  riskFactors: string[];
}

export function AIDetection({ onBack }: Props) {
  const [selected, setSelected] = useState<ResultType | null>(null);
  const [filterRisk, setFilterRisk] = useState("all");

  const data: ResultType[] = [
    {
      id: 1,
      time: "2024-12-15 14:30",
      content: "疑似販售大麻相關對話及圖片",
      drugType: "大麻",
      language: "繁體中文",
      riskLevel: "high",
      score: 95,
      caseNumber: "2025-121401",
      detectedKeywords: ["420", "飛行", "燃料"],
      aiAnalysis: [
        { type: "黑話識別", description: "出現毒品暗語", confidence: 95 },
        { type: "圖像識別", description: "內容物符合大麻外觀", confidence: 97 },
      ],
      riskFactors: ["使用黑話", "公開販售", "高風險毒品"],
    },
    {
      id: 2,
      time: "2024-12-14 18:20",
      content: "高純度粉末圖片",
      drugType: "海洛因",
      language: "英文",
      riskLevel: "high",
      score: 94,
      caseNumber: "2025-121402",
      detectedKeywords: ["純度99%", "交易"],
      aiAnalysis: [
        { type: "交易模式", description: "符合毒品交易模式", confidence: 90 },
      ],
      riskFactors: ["暗網交易", "高純度毒品"],
    },
    {
      id: 3,
      time: "2024-12-13 10:00",
      content: "疑似關鍵字出現",
      drugType: "K他命",
      language: "繁體中文",
      riskLevel: "low",
      score: 40,
      caseNumber: "2025-121403",
      detectedKeywords: ["K"],
      aiAnalysis: [
        { type: "關鍵字", description: "單一關鍵字出現", confidence: 40 },
      ],
      riskFactors: ["證據不足"],
    },
  ];

  const filtered =
    filterRisk === "all"
      ? data
      : data.filter((d) => d.riskLevel === filterRisk);

  const total = data.length;
  const high = data.filter((d) => d.riskLevel === "high").length;
  const medium = data.filter((d) => d.riskLevel === "medium").length;
  const low = data.filter((d) => d.riskLevel === "low").length;
  const avg = Math.round(
    data.reduce((sum, d) => sum + d.score, 0) / data.length
  );

  const getColor = (level: string) => {
    if (level === "high") return "bg-red-500";
    if (level === "medium") return "bg-yellow-500";
    return "bg-gray-400";
  };

  const getText = (level: string) => {
    if (level === "high") return "高風險";
    if (level === "medium") return "中風險";
    return "低風險";
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#2B4C7E] to-[#1a2f4f] p-6">
      <div className="max-w-6xl mx-auto">

        {/* 標題 */}
        <div className="text-center mb-10">
          <h1 className="text-white text-4xl font-bold mb-2">
            多模態毒品交易防制系統
          </h1>
          <p className="text-white/80 text-lg">
            AI自動識別 - 判讀結果
          </p>
        </div>

        <div className="bg-white rounded-3xl p-8 shadow-2xl">

          {/* 返回 */}
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-[#2B4C7E] hover:text-blue-400 mb-6"
          >
            <ArrowLeft />
            返回主頁
          </button>

          {/* 統計卡 */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            <Stat title="總筆數" value={total} />
            <Stat title="高風險" value={high} color="text-red-600" />
            <Stat title="中風險" value={medium} color="text-yellow-600" />
            <Stat title="低風險" value={low} />
            <Stat title="平均分數" value={avg} />
          </div>

          {/* 篩選 */}
          <div className="mb-6">
            <select
              value={filterRisk}
              onChange={(e) => setFilterRisk(e.target.value)}
              className="border-2 border-gray-200 rounded-lg p-2 focus:border-[#2B4C7E]"
            >
              <option value="all">全部</option>
              <option value="high">高風險</option>
              <option value="medium">中風險</option>
              <option value="low">低風險</option>
            </select>
          </div>

          {/* 列表 */}
          <div className="space-y-4">
            {filtered.map((item) => (
              <div
                key={item.id}
                onClick={() => setSelected(item)}
                className="border-2 border-gray-200 p-5 rounded-2xl hover:shadow-lg hover:border-[#2B4C7E] transition cursor-pointer"
              >
                <div className="flex justify-between items-center">
                  <div>
                    <p className="text-sm text-gray-400">{item.time}</p>
                    <p className="text-lg font-medium">{item.content}</p>

                    <div className="flex gap-2 mt-2">
                      <span className="bg-[#2B4C7E] text-white px-3 py-1 rounded-full text-sm">
                        {item.drugType}
                      </span>
                      <span className="bg-purple-100 text-purple-700 px-3 py-1 rounded-full text-sm">
                        {item.language}
                      </span>
                    </div>
                  </div>

                  <div className="text-right">
                    <span
                      className={`px-3 py-1 text-white rounded-full text-sm ${getColor(
                        item.riskLevel
                      )}`}
                    >
                      {getText(item.riskLevel)}
                    </span>
                    <p className="text-xl font-bold mt-2">{item.score}%</p>
                  </div>
                </div>

                {/* 進度條 */}
                <div className="w-full bg-gray-200 h-2 rounded-full mt-4">
                  <div
                    className="bg-[#2B4C7E] h-2 rounded-full"
                    style={{ width: `${item.score}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Modal */}
        {selected && (
          <div className="fixed inset-0 bg-black/60 flex justify-center items-center">
            <div className="bg-white w-[80%] max-w-3xl rounded-2xl overflow-hidden">

              {/* Header */}
              <div className="bg-[#2B4C7E] text-white p-5 flex justify-between">
                <div>
                  <h2 className="text-xl font-bold">詳細分析</h2>
                  <p>案件編號：{selected.caseNumber}</p>
                </div>
                <button onClick={() => setSelected(null)}>✕</button>
              </div>

              <div className="p-6">

                {/* 分數 */}
                <p className="text-lg mb-4">
                  風險分數：<span className="font-bold">{selected.score}%</span>
                </p>

                {/* 關鍵字 */}
                <h3 className="font-semibold mb-2">關鍵字</h3>
                <div className="flex gap-2 flex-wrap mb-4">
                  {selected.detectedKeywords.map((k) => (
                    <span className="bg-red-100 text-red-700 px-3 py-1 rounded-full text-sm">
                      {k}
                    </span>
                  ))}
                </div>

                {/* AI分析 */}
                <h3 className="font-semibold mb-2">AI分析</h3>
                {selected.aiAnalysis.map((a, i) => (
                  <div key={i} className="border rounded-lg p-3 mb-2">
                    <p className="font-medium">{a.type}</p>
                    <p className="text-sm text-gray-600">{a.description}</p>
                    <p className="text-sm text-[#2B4C7E]">
                      信心度 {a.confidence}%
                    </p>
                  </div>
                ))}

                {/* 風險因素 */}
                <h3 className="font-semibold mt-4 mb-2">風險因素</h3>
                <ul className="text-red-600 space-y-1">
                  {selected.riskFactors.map((f, i) => (
                    <li key={i}>● {f}</li>
                  ))}
                </ul>

                <button
                  onClick={() => setSelected(null)}
                  className="mt-6 bg-gray-200 px-4 py-2 rounded-lg"
                >
                  關閉
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ title, value, color = "" }: any) {
  return (
    <div className="bg-gray-50 p-4 rounded-xl text-center shadow-sm">
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-sm text-gray-500">{title}</div>
    </div>
  );
}