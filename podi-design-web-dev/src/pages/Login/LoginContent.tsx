export function LoginContent() {
  return (
    <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden rounded-bl-[120px]">
      <div
        className="absolute inset-0 right-bg-gradient"
        style={{
          background: 'linear-gradient(135deg, #6F2DBD 0%, #A35CFF 50%, #FF4EB7 100%)',
        }}
      />

      <svg className="absolute left-0 top-0 h-full w-auto opacity-20" viewBox="0 0 400 800" preserveAspectRatio="none">
        <path d="M 0 0 Q 100 200, 0 400 T 0 800" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="60" />
        <path d="M 0 100 Q 120 250, 0 450 T 0 850" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="50" />
        <path d="M 0 50 Q 80 180, 0 350 T 0 750" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="70" />
      </svg>

      <svg className="absolute right-0 top-0 h-full w-auto opacity-20" viewBox="0 0 400 800" preserveAspectRatio="none">
        <path d="M 400 0 Q 300 200, 400 400 T 400 800" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="60" />
        <path d="M 400 100 Q 280 250, 400 450 T 400 850" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="50" />
        <path d="M 400 50 Q 320 180, 400 350 T 400 750" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="70" />
      </svg>

      <svg className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-full w-auto opacity-20" viewBox="0 0 300 800" preserveAspectRatio="none">
        <path d="M 150 0 Q 50 200, 150 400 T 150 800" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="80" />
        <path d="M 180 50 Q 80 220, 180 420 T 180 820" fill="none" stroke="rgba(255,255,255,0.18)" strokeWidth="60" />
      </svg>

      <div className="absolute top-0 right-0 w-[700px] h-[700px] bg-[#6F2DBD]/20 rounded-full blur-3xl -translate-y-1/3 translate-x-1/3 blob-top-right" />
      <div className="absolute bottom-0 left-0 w-[800px] h-[800px] bg-[#FF4EB7]/30 rounded-full blur-3xl translate-y-1/3 -translate-x-1/4 blob-bottom-left" />
      <div className="absolute top-1/2 left-1/2 w-[600px] h-[600px] bg-[#A35CFF]/20 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2 blob-center" />
      <div className="absolute top-1/4 right-1/4 w-[400px] h-[400px] bg-white/10 rounded-full blur-2xl blob-white-accent" />
      <div className="absolute bottom-1/4 left-1/3 w-[350px] h-[350px] bg-[#FF8FC9]/15 rounded-full blur-2xl blob-bottom-accent" />

      <div className="relative flex flex-col items-center justify-center p-12 text-white w-full">
        <div className="max-w-lg space-y-8">
          <div className="space-y-4">
            <h2 className="font-bold" style={{ fontSize: 40 }}>POD AI 工具</h2>
          </div>
          <div className="space-y-6 mt-12">
            <ul className="space-y-4">
              <li className="flex items-center gap-4">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-zap w-5 h-5 text-white shrink-0" aria-hidden="true"><path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"></path></svg>
                <span className="text-white/90 text-base leading-relaxed">智能图片处理，一键批量操作</span>
              </li>
              <li className="flex items-center gap-4">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-layers w-5 h-5 text-white shrink-0" aria-hidden="true"><path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"></path><path d="M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"></path><path d="M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"></path></svg>
                <span className="text-white/90 text-base leading-relaxed">多AI工具支持，满足各种需求</span>
              </li>
              <li className="flex items-center gap-4">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-activity w-5 h-5 text-white shrink-0" aria-hidden="true"><path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"></path></svg>
                <span className="text-white/90 text-base leading-relaxed">实时处理跟踪，确保准确性</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginContent;
