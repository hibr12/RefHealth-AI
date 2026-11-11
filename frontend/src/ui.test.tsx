// @vitest-environment jsdom
import {test,expect,vi} from 'vitest';
import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {Form} from './ui';
test('invalid patient age is blocked before submission',async()=>{
  const submit=vi.fn();render(<QueryClientProvider client={new QueryClient()}><Form fields={[{name:'age',label:'Age',type:'number',min:0,max:130}]} onSubmit={submit}/></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText('Age'),{target:{value:'-1'}});fireEvent.submit(screen.getByRole('button',{name:'Save changes'}).closest('form')!);
  await waitFor(()=>expect(screen.getByText(/greater than or equal to 0/)).toBeTruthy());expect(submit).not.toHaveBeenCalled();cleanup();
});
