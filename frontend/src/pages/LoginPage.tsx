import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Phone, ArrowRight, Shield, Globe } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../stores/auth';
import { LanguagePicker } from '../components/LanguagePicker';

export function LoginPage() {
  const [step, setStep] = useState<'phone' | 'otp' | 'language'>('phone');
  const [phone, setPhone] = useState('+');
  const [code, setCode] = useState('');
  const [debugCode, setDebugCode] = useState('');
  const [selectedLang, setSelectedLang] = useState('en');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isNewUser, setIsNewUser] = useState(false);
  const navigate = useNavigate();
  const { setToken, loadUser } = useAuth();

  const handleSendOtp = async () => {
    setError('');
    setLoading(true);
    try {
      const res = await api.sendOtp(phone);
      setDebugCode(res.debug_code);
      setStep('otp');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    setError('');
    setLoading(true);
    try {
      const res = await api.verifyOtp(phone, code);
      setToken(res.access_token, res.user_id);
      setIsNewUser(res.is_new_user);

      if (res.is_new_user) {
        // New user → language selection
        setStep('language');
      } else {
        await loadUser();
        navigate('/chats', { replace: true });
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLanguageSet = async () => {
    setLoading(true);
    try {
      await api.setLanguage(selectedLang);
      await loadUser();
      navigate('/profile', { replace: true });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-[#6C5CE7] to-[#A29BFE] flex items-center justify-center mx-auto mb-4 shadow-lg">
            <span className="text-white text-3xl font-bold">N</span>
          </div>
          <h1 className="text-3xl font-bold text-[var(--nexly-text)]">Nexly</h1>
          <p className="text-[var(--nexly-text-secondary)] mt-1">Fast. Secure. Connected.</p>
        </div>

        {step === 'phone' && (
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-[var(--nexly-text-secondary)] mb-2 block">Phone Number</label>
              <div className="relative">
                <Phone size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--nexly-text-secondary)]" />
                <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+1 234 567 8900"
                  className="w-full pl-12 pr-4 py-3.5 rounded-xl bg-[var(--nexly-surface)] border border-[var(--nexly-border)] text-[var(--nexly-text)] text-lg focus:outline-none focus:border-[var(--nexly-sent)] transition-colors"
                  onKeyDown={(e) => e.key === 'Enter' && handleSendOtp()} />
              </div>
            </div>
            <button onClick={handleSendOtp} disabled={loading || phone.length < 8}
              className="w-full py-3.5 rounded-xl bg-gradient-to-r from-[#6C5CE7] to-[#A29BFE] text-white font-semibold text-lg flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-50 transition-opacity">
              {loading ? 'Sending...' : 'Continue'} <ArrowRight size={20} />
            </button>
          </div>
        )}

        {step === 'otp' && (
          <div className="space-y-4">
            <div className="text-center mb-2">
              <Shield size={40} className="text-[var(--nexly-sent)] mx-auto mb-2" />
              <p className="text-sm text-[var(--nexly-text-secondary)]">
                Enter the code sent to <strong className="text-[var(--nexly-text)]">{phone}</strong>
              </p>
            </div>
            {debugCode && (
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2 text-center">
                <span className="text-xs text-amber-700 dark:text-amber-300">Dev Mode — OTP: </span>
                <span className="font-mono font-bold text-amber-800 dark:text-amber-200">{debugCode}</span>
              </div>
            )}
            <input type="text" inputMode="numeric" maxLength={6} value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} placeholder="000000"
              className="w-full text-center py-4 rounded-xl bg-[var(--nexly-surface)] border border-[var(--nexly-border)] text-[var(--nexly-text)] text-3xl font-mono tracking-[0.5em] focus:outline-none focus:border-[var(--nexly-sent)] transition-colors"
              onKeyDown={(e) => e.key === 'Enter' && handleVerify()} autoFocus />
            <button onClick={handleVerify} disabled={loading || code.length !== 6}
              className="w-full py-3.5 rounded-xl bg-gradient-to-r from-[#6C5CE7] to-[#A29BFE] text-white font-semibold text-lg flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-50 transition-opacity">
              {loading ? 'Verifying...' : 'Verify'}
            </button>
            <button onClick={() => { setStep('phone'); setCode(''); setDebugCode(''); }}
              className="w-full text-center text-sm text-[var(--nexly-text-secondary)] hover:text-[var(--nexly-text)]">
              Change phone number
            </button>
          </div>
        )}

        {step === 'language' && (
          <div className="space-y-5">
            <div className="text-center mb-2">
              <Globe size={40} className="text-[var(--nexly-sent)] mx-auto mb-2" />
              <h2 className="text-xl font-bold text-[var(--nexly-text)]">Choose Your Language</h2>
              <p className="text-sm text-[var(--nexly-text-secondary)] mt-1">
                All messages will be automatically translated<br />to your selected language
              </p>
            </div>

            <LanguagePicker selected={selectedLang} onSelect={setSelectedLang} />

            <div className="bg-[var(--nexly-sent)]/5 border border-[var(--nexly-sent)]/20 rounded-xl p-3">
              <p className="text-xs text-[var(--nexly-text-secondary)] leading-relaxed">
                <Globe size={12} className="inline mr-1 text-[var(--nexly-sent)]" />
                <strong>How it works:</strong> When someone sends you a message in any language,
                Nexly automatically translates it to your language before you see it.
                You always see messages in your own language — seamlessly.
              </p>
            </div>

            <button onClick={handleLanguageSet} disabled={loading}
              className="w-full py-3.5 rounded-xl bg-gradient-to-r from-[#6C5CE7] to-[#A29BFE] text-white font-semibold text-lg flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-50 transition-opacity">
              {loading ? 'Setting up...' : 'Continue'} <ArrowRight size={20} />
            </button>
          </div>
        )}

        {error && <p className="text-red-500 text-sm text-center mt-3">{error}</p>}
      </div>
    </div>
  );
}
