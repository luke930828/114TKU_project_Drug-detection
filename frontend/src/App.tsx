import { useState } from "react";
import { AIDetection } from "./AIDetection";
import { URLAnalysis } from "./URLAnalysis";
import { Report } from "./Report";
import { ReportPreview } from "./ReportPreview";
import WebsiteQuery from "./WebsiteQuery";

export default function App() {
  const [page, setPage] = useState("home");

  // ⭐ 新增這行（關鍵）
  const [reportType, setReportType] = useState<"pdf" | "excel" | null>(null);

  if (page === "ai") return <AIDetection onBack={() => setPage("home")} />;

  if (page === "url") return <URLAnalysis onBack={() => setPage("home")} />;

  if (page === "report")
    return (
      <Report
        onBack={() => setPage("home")}
        onGenerate={(type) => {
          setReportType(type);   // ⭐ 存使用者選擇
          setPage("preview");    // ⭐ 跳轉預覽頁
        }}
      />
    );

  if (page === "preview")
    return (
      <ReportPreview
        onBack={() => setPage("report")}
        type={reportType}   // ⭐ 傳給下一頁
      />
    );

  if (page === "query")
    return <WebsiteQuery onBack={() => setPage("home")} />;

  const cardStyle: React.CSSProperties = {
    backgroundColor: "#ffffff",
    borderRadius: "24px",
    padding: "40px 24px",
    textAlign: "center",
    cursor: "pointer",
    boxShadow: "0 8px 20px rgba(0,0,0,0.15)",
    minHeight: "220px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    transition: "transform 0.2s ease, box-shadow 0.2s ease",
  };

  const titleStyle: React.CSSProperties = {
    fontSize: "22px",
    fontWeight: 700,
    color: "#2B4C7E",
    marginBottom: "12px",
  };

  const descStyle: React.CSSProperties = {
    fontSize: "15px",
    color: "#666666",
    lineHeight: 1.6,
    margin: 0,
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #2B4C7E 0%, #1A2F4F 100%)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "40px 20px",
        boxSizing: "border-box",
      }}
    >
      <h1
        style={{
          color: "#ffffff",
          fontSize: "64px",
          fontWeight: 700,
          margin: "0 0 12px 0",
          textAlign: "center",
        }}
      >
        多模態毒品交易防制系統
      </h1>

      <p
        style={{
          color: "rgba(255,255,255,0.85)",
          fontSize: "20px",
          margin: "20px 0 40px 0",
          textAlign: "center",
        }}
      >
        選擇以下功能
      </p>

      <div
        style={{
          width: "100%",
          maxWidth: "1200px",
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: "28px",
        }}
      >
        <div
          onClick={() => setPage("ai")}
          style={cardStyle}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "translateY(-4px)";
            e.currentTarget.style.boxShadow = "0 12px 28px rgba(0,0,0,0.2)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "0 8px 20px rgba(0,0,0,0.15)";
          }}
        >
          <div style={titleStyle}>AI自動識別</div>
          <p style={descStyle}>使用AI技術自動識別可疑內容</p>
        </div>

        <div
          onClick={() => setPage("url")}
          style={cardStyle}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "translateY(-4px)";
            e.currentTarget.style.boxShadow = "0 12px 28px rgba(0,0,0,0.2)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "0 8px 20px rgba(0,0,0,0.15)";
          }}
        >
          <div style={titleStyle}>輸入網址識別</div>
          <p style={descStyle}>輸入網址進行識別分析</p>
        </div>

        <div
          onClick={() => setPage("report")}
          style={cardStyle}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "translateY(-4px)";
            e.currentTarget.style.boxShadow = "0 12px 28px rgba(0,0,0,0.2)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "0 8px 20px rgba(0,0,0,0.15)";
          }}
        >
          <div style={titleStyle}>合併報表</div>
          <p style={descStyle}>彙整多筆資料並生成報表</p>
        </div>

        <div
          onClick={() => setPage("query")}
          style={cardStyle}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "translateY(-4px)";
            e.currentTarget.style.boxShadow = "0 12px 28px rgba(0,0,0,0.2)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "0 8px 20px rgba(0,0,0,0.15)";
          }}
        >
          <div style={titleStyle}>查詢已識別網站</div>
          <p style={descStyle}>查詢與管理已標記的可疑網站資料庫</p>
        </div>
      </div>

      <p
        style={{
          color: "rgba(255,255,255,0.5)",
          fontSize: "14px",
          marginTop: "36px",
        }}
      >
        © 2024 多模態毒品交易防制系統 ｜ 僅供執法單位使用
      </p>
    </div>
  );
}