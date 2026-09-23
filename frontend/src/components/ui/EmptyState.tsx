import { CircleCheck } from 'lucide-react'

export function EmptyState({ title, message }: { title: string; message: string }) {
  return <div className="state state--empty"><CircleCheck aria-hidden="true" /><div><h3>{title}</h3><p>{message}</p></div></div>
}
