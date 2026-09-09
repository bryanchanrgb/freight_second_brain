import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MarkdownBody({ children }: { children: string }) {
  return (
    <div className="md-body">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children: label }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {label}
            </a>
          ),
          table: ({ children: rows }) => <table className="data">{rows}</table>,
        }}
      >
        {children}
      </Markdown>
    </div>
  );
}
