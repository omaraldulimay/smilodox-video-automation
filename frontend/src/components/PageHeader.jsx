export default function PageHeader({ title, description, wide }) {
  return (
    <div className={wide ? 'page-header page-header-wide' : 'page-header'}>
      <div className="page-header-title">{title}</div>
      {description && <div className="page-header-desc">{description}</div>}
    </div>
  )
}
