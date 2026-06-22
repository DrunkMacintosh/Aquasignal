import MicroLabel from '../ui/MicroLabel.jsx';

export default function SectionTitle({ children }) {
  return <MicroLabel as="h3" className="mb-2.5">{children}</MicroLabel>;
}
