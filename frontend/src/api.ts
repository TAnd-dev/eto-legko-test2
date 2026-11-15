export interface Item {
  id: number;
  name: string;
}

export interface AppConfig {
  campaign_name_prefix: string;
  domain: string;
  group: string;
  source: string;
  keitaro_admin_url: string;
}

export interface CreatedCampaign extends Item {
  alias: string;
  url: string;
  warnings: string[];
}

export interface StreamOffer {
  id: number;
  keitaro_offer_id: number;
  offer_name: string;
  status: "active" | "removed";
  share: number;
  pinned: boolean;
  published_status: "active" | "removed" | null;
  published_share: number | null;
  changed: boolean;
}

export interface Stream {
  id: number;
  keitaro_stream_id: number;
  name: string;
  position: number;
  has_offers: boolean;
  dirty: boolean;
  offers: StreamOffer[];
}

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let message = `Ошибка ${response.status}`;
    try {
      const { detail } = await response.json();
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail))
        message = detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* тело не JSON — оставляем код ответа */
    }
    throw new Error(message);
  }
  return response.json();
}

const q = (value: string) => encodeURIComponent(value);

export const api = {
  config: () => request<AppConfig>("/config"),
  searchOffers: (query: string) => request<Item[]>(`/offers?q=${q(query)}`),
  searchCampaigns: (query: string) => request<Item[]>(`/campaigns?q=${q(query)}`),
  createCampaign: (name: string, geo: string, offerId: number) =>
    request<CreatedCampaign>("/campaigns", "POST", { name, geo, offer_id: offerId }),
  streams: (campaignId: number) => request<Stream[]>(`/campaigns/${campaignId}/streams`),
  fetchStreams: (campaignId: number) =>
    request<Stream[]>(`/campaigns/${campaignId}/fetch-streams`, "POST"),
  addOffer: (streamId: number, offerId: number) =>
    request<Stream>(`/streams/${streamId}/offers`, "POST", { offer_id: offerId }),
  push: (streamId: number) => request<Stream>(`/streams/${streamId}/push`, "POST"),
  cancel: (streamId: number) => request<Stream>(`/streams/${streamId}/cancel`, "POST"),
  remove: (rowId: number) => request<Stream>(`/stream-offers/${rowId}/remove`, "POST"),
  bringBack: (rowId: number) =>
    request<Stream>(`/stream-offers/${rowId}/bring-back`, "POST"),
  pin: (rowId: number, share: number) =>
    request<Stream>(`/stream-offers/${rowId}/pin`, "POST", { share }),
  unpin: (rowId: number) => request<Stream>(`/stream-offers/${rowId}/unpin`, "POST"),
};
