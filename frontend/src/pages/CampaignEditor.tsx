import { useEffect, useState } from "react";
import { api, type Item, type Stream } from "../api";
import Autocomplete from "../components/Autocomplete";
import StreamCard from "../components/StreamCard";

interface Props {
  campaign: Item | null;
  onSelect: (campaign: Item | null) => void;
}

export default function CampaignEditor({ campaign, onSelect }: Props) {
  const [streams, setStreams] = useState<Stream[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [adminUrl, setAdminUrl] = useState("");

  useEffect(() => {
    api
      .config()
      .then((config) => setAdminUrl(config.keitaro_admin_url))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    setStreams([]);
    setError("");
    if (!campaign) return;
    let stale = false;
    api
      .streams(campaign.id)
      .then((loaded) => !stale && setStreams(loaded))
      .catch((e: Error) => !stale && setError(e.message));
    return () => {
      stale = true;
    };
  }, [campaign]);

  async function fetchStreams() {
    if (!campaign) return;
    setBusy(true);
    setError("");
    try {
      setStreams(await api.fetchStreams(campaign.id));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const replace = (updated: Stream) =>
    setStreams((all) => all.map((s) => (s.id === updated.id ? updated : s)));

  return (
    <div>
      <div className="card">
        <h2>Campaign editor</h2>
        <div className="row">
          <Autocomplete
            search={api.searchCampaigns}
            value={campaign}
            onChange={onSelect}
            placeholder="кампания: название или ID"
          />
          <button className="primary" disabled={!campaign || busy} onClick={fetchStreams}>
            {busy ? "Загружаем…" : "Fetch streams from KT"}
          </button>
          <button
            disabled={!campaign || !adminUrl}
            title="Открыть кампанию в Keitaro в новой вкладке"
            onClick={() =>
              campaign &&
              window.open(`${adminUrl}#!/campaign/${campaign.id}/main`, "_blank", "noopener")
            }
          >
            View in KT ↗
          </button>
        </div>
        {error && <p className="error">{error}</p>}
        {campaign && !streams.length && !error && (
          <p className="hint">Потоки ещё не загружены — нажмите Fetch streams from KT.</p>
        )}
      </div>

      {streams.map((stream) => (
        <StreamCard key={stream.id} stream={stream} onChange={replace} />
      ))}
    </div>
  );
}
