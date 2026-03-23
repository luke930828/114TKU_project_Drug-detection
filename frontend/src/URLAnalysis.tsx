import {
  ArrowLeft,
  Search,
  AlertTriangle,
  Eye,
  FileText,
  Cpu,
  RefreshCw,
} from "lucide-react";
import { useState } from "react";

interface URLAnalysisProps {
  onBack: () => void;
}

export function URLAnalysis({ onBack }: URLAnalysisProps) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleAnalyze = () => {
    if (!url) return;

    setLoading(true);
    setResult(null);

    // 模擬 AI 分析
    setTimeout(() => {
      const fakeResult = {
        score: 98.5,
        risk: "HIGH",
        keywords: [
          { word: "420", count: 15 },
          { word: "飛行", count: 8 },
          { word: "埋包", count: 3 },
        ],
        summary: "偵測到毒品交易語意與影像特徵，疑似非法交易。",
      };

      setResult(fakeResult);
      setLoading(false);
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#2B4C7E] to-[#1a2f4f] p-6">
      <div className="max-w-7xl mx-auto">

        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <button onClick={onBack} className="text-white flex gap-2">
            <ArrowLeft /> 返回主頁
          </button>
          <h1 className="text-white text-2xl font-bold">
            URL 智能風險分析
          </h1>
        </div>

        {/* 輸入框 */}
        <div className="bg-[#1e3a63]/80 p-4 rounded-xl flex gap-4 mb-6">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="輸入可疑網址..."
            className="flex-1 px-4 py-2 rounded bg-[#0f2342] text-white"
          />

          <button
            onClick={handleAnalyze}
            className="bg-blue-500 px-6 py-2 rounded text-white flex gap-2"
          >
            {loading ? <RefreshCw className="animate-spin" /> : <Search />}
            分析
          </button>
        </div>

        {/* Loading */}
        {loading && (
          <div className="text-white text-center">AI 分析中...</div>
        )}

        {/* 結果 */}
        {result && (
          <div className="space-y-6">

            {/* 風險 */}
            <div className="bg-red-900 p-6 rounded-xl flex justify-between text-white">
              <div>
                <div>風險判定</div>
                <h2 className="text-3xl font-bold">
                  {result.risk} RISK
                </h2>
              </div>
              <div className="text-5xl">{result.score}</div>
            </div>

            {/* YOLO + BERT */}
            <div className="grid grid-cols-2 gap-6">

              {/* YOLO */}
              <div className="bg-[#0f2342] p-6 rounded-xl text-white">
                <h3 className="mb-4 flex gap-2">
                  <Eye /> YOLO 視覺偵測
                </h3>

                <div className="bg-black h-48 flex items-center justify-center">
                  模擬圖片辨識
                </div>
              </div>

              {/* BERT */}
              <div className="bg-[#0f2342] p-6 rounded-xl text-white">
                <h3 className="mb-4 flex gap-2">
                  <FileText /> 語意分析
                </h3>

                {result.keywords.map((k: any, i: number) => (
                  <div key={i} className="flex justify-between">
                    <span>{k.word}</span>
                    <span>{k.count}</span>
                  </div>
                ))}

                <div className="mt-4 bg-[#1e3a63] p-3 rounded">
                  <Cpu /> {result.summary}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}