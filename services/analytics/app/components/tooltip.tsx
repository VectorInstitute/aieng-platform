import { ReactNode, useState } from 'react';

interface TooltipProps {
  content: string;
  children: ReactNode;
  position?: 'left' | 'center' | 'right';
}

export function Tooltip({ content, children, position = 'center' }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);

  // Position classes for tooltip container
  const positionClasses = {
    left: 'left-0',
    center: 'left-1/2 -translate-x-1/2',
    right: 'right-0',
  };

  // Position classes for arrow
  const arrowPositionClasses = {
    left: 'left-4',
    center: 'left-1/2 -translate-x-1/2',
    right: 'right-4',
  };

  return (
    <div className="relative inline-block">
      <div
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        className="cursor-help"
      >
        {children}
      </div>
      {isVisible && (
        <div className={`absolute z-50 top-full mt-2 px-3 py-2 text-xs font-normal text-white bg-slate-900 dark:bg-slate-700 rounded-lg shadow-xl w-max max-w-[280px] text-left normal-case ${positionClasses[position]}`}>
          {content}
          <div className={`absolute bottom-full -mb-1 ${arrowPositionClasses[position]}`}>
            <div className="border-4 border-transparent border-b-slate-900 dark:border-b-slate-700"></div>
          </div>
        </div>
      )}
    </div>
  );
}
