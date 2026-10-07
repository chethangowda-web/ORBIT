"use client";

import React, { useEffect, useState } from "react";
import { Search, X } from "lucide-react";

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChange,
  placeholder = "Search tasks...",
}) => {
  const [innerVal, setInnerVal] = useState(value);

  // 300ms debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      onChange(innerVal);
    }, 300);
    return () => clearTimeout(timer);
  }, [innerVal, onChange]);

  useEffect(() => {
    setInnerVal(value);
  }, [value]);

  return (
    <div className="relative flex-1 min-w-[200px]">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
      <input
        type="text"
        value={innerVal}
        onChange={(e) => setInnerVal(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-9 pr-8 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-100 placeholder-slate-500 text-xs focus:outline-none focus:border-indigo-500 transition-colors"
      />
      {innerVal && (
        <button
          onClick={() => {
            setInnerVal("");
            onChange("");
          }}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
};
