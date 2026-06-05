'use client';

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';

export default function DocsPage() {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDocs = async () => {
      try {
        const response = await fetch('http://localhost:9102/api/docs/reference');
        if (!response.ok) {
          throw new Error(`Failed to fetch docs: ${response.status}`);
        }
        const text = await response.text();
        setContent(text);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchDocs();
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <div className="sticky top-0 z-10 flex items-center gap-3 px-6 py-3 border-b bg-background/95 backdrop-blur">
        <h1 className="text-lg font-semibold">API Reference</h1>
        <a
          href="http://localhost:9102/api/docs/reference"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-muted-foreground underline hover:text-foreground"
        >
          Raw Markdown
        </a>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8">
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-foreground" />
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-4">
            <p className="text-sm text-destructive font-medium">Failed to load documentation</p>
            <p className="text-sm text-muted-foreground mt-1">{error}</p>
          </div>
        )}

        {!loading && !error && content && (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown
              components={{
                h1: ({ node, ...props }) => <h1 className="text-3xl font-bold mt-8 mb-4" {...props} />,
                h2: ({ node, ...props }) => <h2 className="text-2xl font-bold mt-6 mb-3" {...props} />,
                h3: ({ node, ...props }) => <h3 className="text-xl font-semibold mt-4 mb-2" {...props} />,
                h4: ({ node, ...props }) => <h4 className="text-lg font-semibold mt-3 mb-2" {...props} />,
                p: ({ node, ...props }) => <p className="my-3 text-muted-foreground" {...props} />,
                a: ({ node, ...props }) => (
                  <a className="text-primary underline hover:text-primary/80" target="_blank" rel="noopener noreferrer" {...props} />
                ),
                code: ({ node, className, ...props }) => {
                  if (!className) {
                    return <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono" {...props} />;
                  }
                  return <code className="bg-muted p-3 rounded-lg block text-sm font-mono overflow-x-auto my-3" {...props} />;
                },
                pre: ({ node, ...props }) => (
                  <pre className="bg-muted p-4 rounded-lg overflow-x-auto text-sm font-mono my-3" {...props} />
                ),
                ul: ({ node, ...props }) => <ul className="list-disc list-inside space-y-2 my-3" {...props} />,
                ol: ({ node, ...props }) => <ol className="list-decimal list-inside space-y-2 my-3" {...props} />,
                li: ({ node, ...props }) => <li className="text-muted-foreground" {...props} />,
                blockquote: ({ node, ...props }) => (
                  <blockquote className="border-l-4 border-muted pl-4 italic text-muted-foreground my-3" {...props} />
                ),
                table: ({ node, ...props }) => (
                  <div className="overflow-x-auto my-4">
                    <table className="w-full border-collapse" {...props} />
                  </div>
                ),
                th: ({ node, ...props }) => <th className="border px-4 py-2 bg-muted text-left font-semibold" {...props} />,
                td: ({ node, ...props }) => <td className="border px-4 py-2" {...props} />,
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}

        {!loading && !error && !content && (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No documentation available</p>
          </div>
        )}
      </div>
    </div>
  );
}
