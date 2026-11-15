import { useEffect, useState } from "react";
import { api, type Item, type Stream, type StreamOffer } from "../api";
import Autocomplete from "./Autocomplete";

interface Props {
  stream: Stream;
  onChange: (stream: Stream) => void;
}

export default function StreamCard({ stream, onChange }: Props) {
  const [offer, setOffer] = useState<Item | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(action: () => Promise<Stream>) {
    setBusy(true);
    setError("");
    try {
      onChange(await action());
      return true;
    } catch (err) {
      setError((err as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  if (!stream.has_offers) {
    return (
      <section className="card stream">
        <header>
          <h3>{stream.name}</h3>
          <span className="muted">поток без офферов</span>
        </header>
      </section>
    );
  }

  const total = stream.offers.reduce((sum, o) => sum + o.share, 0);

  return (
    <section className={`card stream ${stream.dirty ? "dirty" : ""}`}>
      <header>
        <h3>{stream.name}</h3>
        <span className={stream.dirty ? "badge warn" : "badge"}>
          {stream.dirty ? "не опубликован" : "опубликован"}
        </span>
      </header>

      <table>
        <thead>
          <tr>
            <th>Оффер</th>
            <th className="num">Доля</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {stream.offers.map((row) => (
            <OfferRow key={row.id} row={row} busy={busy} run={run} />
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>Итого</td>
            <td className="num">{total}%</td>
            <td />
          </tr>
        </tfoot>
      </table>

      <div className="row">
        <Autocomplete
          search={api.searchOffers}
          value={offer}
          onChange={setOffer}
          placeholder="добавить оффер: название или ID"
        />
        <button
          disabled={!offer || busy}
          onClick={async () => {
            if (offer && (await run(() => api.addOffer(stream.id, offer.id)))) setOffer(null);
          }}
        >
          Add
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="row end">
        <button disabled={!stream.dirty || busy} onClick={() => run(() => api.cancel(stream.id))}>
          Cancel
        </button>
        <button
          className="primary"
          disabled={!stream.dirty || busy}
          onClick={() => run(() => api.push(stream.id))}
        >
          Push to Keitaro
        </button>
      </div>
    </section>
  );
}

interface RowProps {
  row: StreamOffer;
  busy: boolean;
  run: (action: () => Promise<Stream>) => Promise<boolean>;
}

function OfferRow({ row, busy, run }: RowProps) {
  const [share, setShare] = useState(String(row.share));
  useEffect(() => setShare(String(row.share)), [row.share]);

  const title = `[${row.keitaro_offer_id}] ${row.offer_name}`;

  if (row.status === "removed") {
    return (
      <tr className="removed">
        <td>
          {title}
          {row.published_status === "active" && <span className="tag">удаление не опубликовано</span>}
        </td>
        <td className="num">0%</td>
        <td className="actions">
          <button disabled={busy} onClick={() => run(() => api.bringBack(row.id))}>
            Bring back
          </button>
        </td>
      </tr>
    );
  }

  const value = Number(share);
  const valid = Number.isInteger(value) && value >= 1 && value <= 100;
  // Введённое число само ничего не меняет: доля применяется закреплением.
  const edited = share !== String(row.share);
  const applyShare = () => run(() => api.pin(row.id, value));

  return (
    <tr>
      <td>
        {title}
        {row.published_status !== "active" && <span className="tag">новый</span>}
      </td>
      <td className="num">
        <input
          className={`share ${edited ? "edited" : ""}`}
          type="number"
          min={1}
          max={100}
          value={share}
          disabled={busy}
          onChange={(e) => setShare(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && edited && valid) applyShare();
            if (e.key === "Escape") setShare(String(row.share));
          }}
        />
        %
      </td>
      <td className="actions">
        {edited ? (
          <button className="primary" disabled={busy || !valid} onClick={applyShare}>
            {valid ? `Закрепить ${value}%` : "1–100"}
          </button>
        ) : row.pinned ? (
          <button disabled={busy} onClick={() => run(() => api.unpin(row.id))}>
            📌 Unpin
          </button>
        ) : (
          <button disabled={busy} onClick={applyShare}>
            Pin
          </button>
        )}
        <button disabled={busy} onClick={() => run(() => api.remove(row.id))}>
          Remove
        </button>
      </td>
    </tr>
  );
}
