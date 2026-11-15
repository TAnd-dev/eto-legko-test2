import { useEffect, useRef, useState } from "react";
import type { Item } from "../api";

interface Props {
  search: (query: string) => Promise<Item[]>;
  value: Item | null;
  onChange: (item: Item | null) => void;
  placeholder?: string;
}

const label = (item: Item) => `[${item.id}] ${item.name}`;

export default function Autocomplete({ search, value, onChange, placeholder }: Props) {
  const [text, setText] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const requestId = useRef(0);

  useEffect(() => {
    setText(value ? label(value) : "");
  }, [value]);

  useEffect(() => {
    if (!open) return;
    const id = ++requestId.current;
    const query = value && text === label(value) ? "" : text;
    const timer = setTimeout(() => {
      search(query)
        .then((found) => {
          if (id === requestId.current) {
            setItems(found);
            setError("");
          }
        })
        .catch((e: Error) => id === requestId.current && setError(e.message));
    }, 200);
    return () => clearTimeout(timer);
  }, [text, open, search, value]);

  return (
    <div className="autocomplete">
      <input
        value={text}
        placeholder={placeholder}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
          if (value) onChange(null);
        }}
      />
      {open && (
        <ul className="autocomplete-list">
          {error && <li className="muted">{error}</li>}
          {!error && items.length === 0 && <li className="muted">Ничего не найдено</li>}
          {items.map((item) => (
            <li
              key={item.id}
              onMouseDown={(e) => {
                e.preventDefault();
                onChange(item);
                setText(label(item));
                setOpen(false);
              }}
            >
              {label(item)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
