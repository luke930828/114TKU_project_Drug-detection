import { useEffect, useState } from "react";
import { AIDetection } from "./AIDetection";
import { URLAnalysis } from "./URLAnalysis";
import { Report } from "./Report";
import WebsiteQuery, { type PendingWebsite } from "./WebsiteQuery";
import Login from "./Login";
import UserManagement from "./UserManagement";
import {
  AUTH_UNAUTHORIZED_EVENT,
  clearAuthToken,
  getAuthToken,
} from "./auth";

export default function App() {
  const [page, setPage] = useState("home");
  const [blacklist, setBlacklist] = useState<string[]>(["dark-market-x.onion"]);
  const [whitelist, setWhitelist] = useState<string[]>(["google.com"]);
  const [pendingSites, setPendingSites] = useState<PendingWebsite[]>([]);

  const [isAuthenticated, setIsAuthenticated] = useState(
    Boolean(getAuthToken())
  );

  const handleLogout = () => {
    clearAuthToken();
    setIsAuthenticated(false);
    setPage("home");
  };

  useEffect(() => {
    const handleUnauthorized = () => {
      setIsAuthenticated(false);
      setPage("home");
    };

    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => {
      window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    };
  }, []);

  if (!isAuthenticated) {
    return <Login onLogin={() => setIsAuthenticated(true)} />;
  }
  if (page === "ai")
    return (
      <AIDetection
        onBack={() => setPage("home")}
        onDetectionsLoaded={(sites) => {
          const highRiskUrls = new Set(
            sites
              .filter((site) => site.riskLevel === "高風險")
              .map((site) => site.url)
          );
          const mediumRiskSites = sites.filter(
            (site) => site.riskLevel === "中風險"
          );

          setBlacklist((current) =>
            Array.from(new Set([...current, ...highRiskUrls]))
          );
          setWhitelist((current) =>
            current.filter((url) => !highRiskUrls.has(url))
          );
          setPendingSites((current) => {
            const merged = new Map(
              current
                .filter(
                  (site) =>
                    site.riskLevel === "中風險" &&
                    !highRiskUrls.has(site.url)
                )
                .map((site) => [site.url, site])
            );

            mediumRiskSites.forEach((site) => {
              if (!blacklist.includes(site.url) && !whitelist.includes(site.url)) {
                merged.set(site.url, site);
              }
            });

            return Array.from(merged.values()).sort(
              (first, second) => second.score - first.score
            );
          });
        }}
      />
    );

  if (page === "url") return <URLAnalysis onBack={() => setPage("home")} />;


  if (page === "report")
    return (
      <Report
        onBack={() => setPage("home")}
      />
    );

  if (page === "query")
    return (
      <WebsiteQuery
        onBack={() => setPage("home")}
        blacklist={blacklist}
        pendingSites={pendingSites}
        onAdd={(type, url) => {
          if (type === "black") {
            setBlacklist((current) => current.includes(url) ? current : [...current, url]);
            setWhitelist((current) => current.filter((item) => item !== url));
          } else {
            setWhitelist((current) => current.includes(url) ? current : [...current, url]);
            setBlacklist((current) => current.filter((item) => item !== url));
          }
          setPendingSites((current) => current.filter((item) => item.url !== url));
        }}
        onRemove={(type, url) => {
          if (type === "black") setBlacklist((current) => current.filter((item) => item !== url));
          else setWhitelist((current) => current.filter((item) => item !== url));
        }}
        onClassify={(url, type) => {
          if (type === "black") {
            setBlacklist((current) => current.includes(url) ? current : [...current, url]);
            setWhitelist((current) => current.filter((item) => item !== url));
          } else {
            setWhitelist((current) => current.includes(url) ? current : [...current, url]);
            setBlacklist((current) => current.filter((item) => item !== url));
          }
          setPendingSites((current) => current.filter((item) => item.url !== url));
        }}
      />
    );

  if (page === "users")
    return (
      <UserManagement
        onBack={() => setPage("home")}
        onUnauthorized={handleLogout}
      />
    );

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
      <button
        type="button"
        onClick={handleLogout}
        style={{
          position: "absolute",
          top: "24px",
          right: "28px",
          background: "rgba(255,255,255,0.12)",
          border: "1px solid rgba(255,255,255,0.35)",
          borderRadius: "10px",
          color: "white",
          padding: "9px 16px",
          cursor: "pointer",
        }}
      >
        登出
      </button>
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
          <div style={titleStyle}>24小時AI自動識別</div>
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

        <div
          onClick={() => setPage("users")}
          style={{ ...cardStyle, gridColumn: "1 / -1" }}
          onMouseEnter={(event) => {
            event.currentTarget.style.transform = "translateY(-4px)";
            event.currentTarget.style.boxShadow = "0 12px 28px rgba(0,0,0,0.2)";
          }}
          onMouseLeave={(event) => {
            event.currentTarget.style.transform = "translateY(0)";
            event.currentTarget.style.boxShadow = "0 8px 20px rgba(0,0,0,0.15)";
          }}
        >
          <div style={titleStyle}>人員與權限管理</div>
          <p style={descStyle}>新增人員、調整權限及管理帳號狀態</p>
        </div>
      </div>

      <p
        style={{
          color: "rgba(255,255,255,0.5)",
          fontSize: "14px",
          marginTop: "36px",
        }}
      >
        多模態毒品交易防制系統 ｜ 僅供執法單位使用
      </p>
    </div>
  );
}
