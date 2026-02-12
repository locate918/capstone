import { render, screen } from '@testing-library/react';

jest.mock('./services/api', () => ({
  fetchEvents: jest.fn().mockResolvedValue([]),
  smartSearch: jest.fn().mockResolvedValue({ events: [], parsed: {} }),
}));

jest.mock('./components/Header', () => function MockHeader() {
  return <div>Header</div>;
});

jest.mock('./components/TulsaMap', () => function MockTulsaMap() {
  return <div>Map</div>;
});

jest.mock('./components/AIChatWidget', () => function MockAIChatWidget() {
  return <div>AI Chat</div>;
});

jest.mock('./components/EventCard', () => function MockEventCard() {
  return <div>Event Card</div>;
});

jest.mock('./components/EventModal', () => function MockEventModal() {
  return null;
});

import App from './App';

test('renders trending collections heading', () => {
  render(<App />);
  expect(screen.getByText(/trending collections/i)).toBeInTheDocument();
});
