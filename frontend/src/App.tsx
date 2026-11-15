import { useEffect, useState } from "react";
import type { Item } from "./api";
import CampaignEditor from "./pages/CampaignEditor";
import CreateCampaign from "./pages/CreateCampaign";

type Tab = "create" | "editor";

// Вкладка и выбранная кампания переживают обновление страницы.
// Сами потоки и черновики хранит бэкенд — они подгружаются по ID кампании.
const STORAGE_KEY = "keitaro-wrapper:view";

interface SavedView {
  tab: Tab;
  campaign: Item | null;
}

function loadView(): SavedView {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    const campaign =
      typeof saved?.campaign?.id === "number" && typeof saved.campaign.name === "string"
        ? { id: saved.campaign.id, name: saved.campaign.name }
        : null;
    return { tab: saved?.tab === "editor" ? "editor" : "create", campaign };
  } catch {
    return { tab: "create", campaign: null };
  }
}

export default function App() {
  const [initial] = useState(loadView);
  const [tab, setTab] = useState<Tab>(initial.tab);
  const [campaign, setCampaign] = useState<Item | null>(initial.campaign);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ tab, campaign }));
    } catch {
      /* хранилище недоступно (приватный режим) — просто не запоминаем */
    }
  }, [tab, campaign]);

  return (
    <main>
      <nav>
        <button className={tab === "create" ? "active" : ""} onClick={() => setTab("create")}>
          Новая кампания
        </button>
        <button className={tab === "editor" ? "active" : ""} onClick={() => setTab("editor")}>
          Редактор офферов
        </button>
      </nav>

      <div hidden={tab !== "create"}>
        <CreateCampaign
          onOpenEditor={(created) => {
            setCampaign({ id: created.id, name: created.name });
            setTab("editor");
          }}
        />
      </div>
      <div hidden={tab !== "editor"}>
        <CampaignEditor campaign={campaign} onSelect={setCampaign} />
      </div>
    </main>
  );
}
