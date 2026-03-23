import { useState } from "react";
import { ArrowLeft, FileText, FileSpreadsheet, Calendar } from "lucide-react";

interface Props {
  onBack: () => void;
  onGenerate: (type: "pdf" | "excel") => void;
}

export function Report({ onBack, onGenerate }: Props) {
  const [format, setFormat] = useState<"pdf" | "excel" | null>(null);
  const [range, setRange] = useState<"season" | "year" | "custom" | null>(null);

  const isReady = format && range;

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#2B4C7E] to-[#1a2f4f] flex justify-center items-center p-6">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-2xl">

        {/* 返回 */}
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-gray-500 hover:text-blue-500 mb-6"
        >
          <ArrowLeft className="w-5 h-5" />
          返回主頁
        </button>

        {/* 標題 */}
        <h1 className="text-xl font-bold text-gray-800 mb-4">
          選擇報表格式
        </h1>

        {/* 說明 */}
        <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg mb-6 text-sm text-blue-700">
          包含AI偵測案件統計、毒品類別分布、趨勢分析圖表、關鍵績效指標(KPI)及執法建議。
        </div>

        {/* 格式 */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          
          <div
            onClick={() => setFormat("pdf")}
            className={`cursor-pointer border rounded-xl p-6 text-center transition
              ${format === "pdf"
                ? "border-blue-500 bg-blue-50"
                : "border-gray-200 hover:border-blue-300"}
            `}
          >
            <FileText className="w-8 h-8 mx-auto text-blue-500 mb-2" />
            <div className="font-bold">PDF</div>
            <div className="text-sm text-gray-400">適合簡報與存檔</div>
          </div>

          <div
            onClick={() => setFormat("excel")}
            className={`cursor-pointer border rounded-xl p-6 text-center transition
              ${format === "excel"
                ? "border-blue-500 bg-blue-50"
                : "border-gray-200 hover:border-blue-300"}
            `}
          >
            <FileSpreadsheet className="w-8 h-8 mx-auto text-green-500 mb-2" />
            <div className="font-bold">Excel</div>
            <div className="text-sm text-gray-400">適合數據分析</div>
          </div>
        </div>

        {/* 時間範圍 */}
        <h2 className="text-lg font-bold text-gray-800 mb-4">
          選擇時間範圍
        </h2>

        <div className="grid grid-cols-3 gap-4 mb-8">

          <div
            onClick={() => setRange("season")}
            className={`cursor-pointer border rounded-xl p-5 text-center
              ${range === "season"
                ? "border-blue-500 bg-blue-50"
                : "border-gray-200 hover:border-blue-300"}
            `}
          >
            <div className="font-bold">季度報表</div>
            <div className="text-sm text-gray-400">Q1-Q4</div>
          </div>

          <div
            onClick={() => setRange("year")}
            className={`cursor-pointer border rounded-xl p-5 text-center
              ${range === "year"
                ? "border-blue-500 bg-blue-50"
                : "border-gray-200 hover:border-blue-300"}
            `}
          >
            <div className="font-bold">年度報表</div>
            <div className="text-sm text-gray-400">全年</div>
          </div>

          <div
            onClick={() => setRange("custom")}
            className={`cursor-pointer border rounded-xl p-5 text-center
              ${range === "custom"
                ? "border-blue-500 bg-blue-50"
                : "border-gray-200 hover:border-blue-300"}
            `}
          >
            <Calendar className="w-5 h-5 mx-auto mb-1 text-gray-500" />
            <div className="font-bold">自訂範圍</div>
            <div className="text-sm text-gray-400">選擇日期</div>
          </div>

        </div>

        {/* 按鈕 */}
        <button
  onClick={() => {
    if (format) onGenerate(format);
  }}
  disabled={!isReady}
  className={`w-full py-3 rounded-xl font-bold transition
    ${isReady
      ? "bg-blue-500 hover:bg-blue-600 text-white"
      : "bg-gray-200 text-gray-400 cursor-not-allowed"}
  `}
>
  生成報表
</button>

      </div>
    </div>
  );
}