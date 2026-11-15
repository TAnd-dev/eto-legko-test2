import { useEffect, useState } from "react";
import { api, type AppConfig, type CreatedCampaign, type Item } from "../api";
import Autocomplete from "../components/Autocomplete";

interface Props {
  onOpenEditor: (campaign: Item) => void;
}

export default function CreateCampaign({ onOpenEditor }: Props) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [name, setName] = useState("");
  const [geo, setGeo] = useState("");
  const [offer, setOffer] = useState<Item | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<CreatedCampaign | null>(null);

  useEffect(() => {
    api.config().then(setConfig).catch(() => undefined);
  }, []);

  const prefix = config?.campaign_name_prefix ?? "";
  const trimmed = name.trim();
  const finalName = trimmed && prefix && !trimmed.startsWith(prefix) ? prefix + trimmed : trimmed;
  const ready = trimmed && geo.trim() && offer && !busy;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!offer) return;
    setBusy(true);
    setError("");
    setCreated(null);
    try {
      setCreated(await api.createCampaign(name, geo, offer.id));
      setName("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
      <h2>New campaign</h2>

      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="имя кампании" />
        {finalName && finalName !== trimmed && (
          <span className="hint">Будет создана как «{finalName}»</span>
        )}
      </label>

      <label>
        Geo
        <input value={geo} onChange={(e) => setGeo(e.target.value)} placeholder="MX, AU, RO…" />
        <span className="hint">Двухбуквенный код страны; несколько — через запятую</span>
      </label>

      <label>
        Offer
        <Autocomplete
          search={api.searchOffers}
          value={offer}
          onChange={setOffer}
          placeholder="поиск по названию или ID"
        />
      </label>

      {config && (
        <p className="hint">
          Домен {config.domain}, группа {config.group}, источник {config.source}
        </p>
      )}

      <button className="primary" disabled={!ready}>
        {busy ? "Создаём…" : "Create"}
      </button>

      {error && <p className="error">{error}</p>}
      {created && (
        <div className="success">
          <p>
            Кампания «{created.name}» создана (ID {created.id}).
          </p>
          <p>
            <a href={created.url} target="_blank" rel="noreferrer">
              {created.url}
            </a>
          </p>
          {created.warnings.map((warning) => (
            <p key={warning} className="warning">
              ⚠ {warning}
            </p>
          ))}
          <button type="button" onClick={() => onOpenEditor(created)}>
            Открыть в редакторе
          </button>
        </div>
      )}
    </form>
  );
}
